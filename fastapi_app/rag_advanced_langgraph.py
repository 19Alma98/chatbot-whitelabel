"""
LangGraph-based implementation of Advanced RAG Chat.

This module transforms the AdvancedRAGChat into a LangGraph agent with:
- Explicit state management
- Graph-based workflow with nodes for each step
- Better observability and extensibility
- Support for conditional routing and loops
"""

from collections.abc import AsyncGenerator
from typing import Annotated, Any, TypedDict
import operator
import logging

from langgraph.graph import StateGraph, END, START
from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
)
from openai_messages_token_helper import build_messages, get_token_limit

from fastapi_app.api_models import (
    AIChatRoles,
    Message,
    RAGContext,
    RetrievalResponse,
    RetrievalResponseDelta,
    ThoughtStep,
    ChatParams,
)
from fastapi_app.protocols import DocumentProtocol, SearcherProtocol
from fastapi_app.query_rewriter import build_search_function, extract_search_arguments
from fastapi_app.rag_base import RAGChatBase

logger = logging.getLogger("ragapp")


class RAGState(TypedDict):
    """State that flows through the RAG agent graph."""
    
    # Input parameters
    chat_params: ChatParams
    
    # Query rewriting step outputs
    query_messages: list[ChatCompletionMessageParam]
    rewritten_query: str | None
    filters: list[Any]
    
    # Search step outputs
    search_results: list[DocumentProtocol]
    
    # Context building step outputs
    contextual_messages: list[ChatCompletionMessageParam]
    
    # Thoughts for observability
    thoughts: Annotated[list[ThoughtStep], operator.add]
    
    # Final outputs
    final_answer: str | None
    error: str | None


class AdvancedRAGChatLangGraph(RAGChatBase):
    """
    LangGraph-based RAG Chat implementation.
    
    This class uses LangGraph to orchestrate the RAG workflow as a state machine
    with explicit nodes for each processing step.
    
    - Simple mode: Direct search using original user query (no query rewriting)
    - Advanced mode: Query rewriting with function calling, then search with filters
    """
    
    def __init__(
        self,
        *,
        searcher: SearcherProtocol,
        openai_chat_client: AsyncOpenAI | AsyncAzureOpenAI,
        chat_model: str,
        chat_deployment: str | None,  # Not needed for non-Azure OpenAI
        use_advanced_flow: bool = True,
    ):
        self.searcher: SearcherProtocol = searcher
        self.openai_chat_client = openai_chat_client
        self.chat_model = chat_model
        self.chat_deployment = chat_deployment
        self.chat_token_limit = get_token_limit(chat_model, default_to_minimum=True)
        
        # Cache the search function tools (constant, no need to rebuild)
        self._search_tools = build_search_function()
        
        # Cache compiled graphs for both modes (built lazily on first use)
        self._graph_advanced: Any | None = None
        self._graph_simple: Any | None = None
    
    def _build_graph(self, use_advanced_flow: bool) -> Any:
        """
        Build or retrieve cached LangGraph state machine for the RAG workflow.
        
        Args:
            use_advanced_flow: If True, includes query rewriting step. If False, uses simple direct search.
        
        Returns:
            Compiled graph for the requested mode (cached after first build).
        """
        if use_advanced_flow and self._graph_advanced is not None:
            return self._graph_advanced
        if not use_advanced_flow and self._graph_simple is not None:
            return self._graph_simple
        
        workflow = StateGraph(RAGState)
        workflow.add_node("document_retrieval", self._document_retrieval_node)
        workflow.add_node("context_assembly", self._context_assembly_node)
        
        if use_advanced_flow:
            workflow.add_node("query_rewriting", self._query_rewriting_node)
            workflow.add_edge(START, "query_rewriting")
            workflow.add_edge("query_rewriting", "document_retrieval")
        else:
            workflow.add_edge(START, "document_retrieval")
        
        workflow.add_edge("document_retrieval", "context_assembly")
        workflow.add_edge("context_assembly", END)
        
        compiled_graph = workflow.compile()
        if use_advanced_flow:
            self._graph_advanced = compiled_graph
        else:
            self._graph_simple = compiled_graph
        
        return compiled_graph
    
    def _create_initial_state(self, chat_params: ChatParams) -> RAGState:
        """Create initial state for the LangGraph workflow."""
        return {
            "chat_params": chat_params,
            "query_messages": [],
            "rewritten_query": None,
            "filters": [],
            "search_results": [],
            "contextual_messages": [],
            "thoughts": [],
            "final_answer": None,
            "error": None,
        }
    
    async def _query_rewriting_node(self, state: RAGState) -> dict[str, Any]:
        """
        Node 1: Query Rewriting
        
        Generate an optimized search query using function calling based on
        the chat history and the user's question.
        
        On error, falls back to using the original user query.
        """
        chat_params = state["chat_params"]
        
        try:
            tools = self._search_tools
            tool_choice = "auto"
            
            query_messages: list[ChatCompletionMessageParam] = build_messages(
                model=self.chat_model,
                system_prompt=self.query_prompt_template,
                few_shots=self.query_fewshots,
                new_user_content=chat_params.original_user_query,
                past_messages=chat_params.past_messages,
                max_tokens=self.chat_token_limit,
                tools=tools,
                tool_choice=tool_choice,
                fallback_to_default=True,
            )
            
            chat_completion: ChatCompletion = await self.openai_chat_client.chat.completions.create(
                messages=query_messages,
                model=self.chat_deployment if self.chat_deployment else self.chat_model,
                temperature=0.0,  # Minimize creativity for search query generation
                max_tokens=chat_params.response_token_limit,
                n=1,
                tools=tools,
                tool_choice=tool_choice,
                seed=chat_params.seed,
            )
            
            query_text, filters = extract_search_arguments(
                chat_params.original_user_query, chat_completion
            )
            
            # Validate extracted query
            if not query_text or not query_text.strip():
                logger.warning("Query rewriting returned empty query, falling back to original")
                query_text = chat_params.original_user_query
                filters = []
            
            thought = ThoughtStep(
                title="Query Rewriting (LangGraph - Advanced Mode)",
                description=query_messages,
                props={
                    "model": self.chat_model,
                    "deployment": self.chat_deployment,
                    "rewritten_query": query_text,
                    "filters": filters,
                } if self.chat_deployment else {
                    "model": self.chat_model,
                    "rewritten_query": query_text,
                    "filters": filters,
                },
            )
            
            return {
                "query_messages": query_messages,
                "rewritten_query": query_text,
                "filters": filters,
                "thoughts": [thought],
            }
        except Exception as e:
            logger.error(f"Error in query rewriting node: {e}", exc_info=True)
            fallback_thought = ThoughtStep(
                title="Query Rewriting (LangGraph - Advanced Mode - Fallback)",
                description=f"Query rewriting failed: {str(e)}",
                props={
                    "error": str(e),
                    "fallback": True,
                    "using_original_query": True,
                },
            )
            return {
                "query_messages": [],
                "rewritten_query": chat_params.original_user_query,
                "filters": [],
                "thoughts": [fallback_thought],
            }
    
    async def _document_retrieval_node(self, state: RAGState) -> dict[str, Any]:
        """
        Document Retrieval Node
        
        Retrieve relevant documents from the vector database.
        In advanced mode: uses rewritten query and filters.
        In simple mode: uses original user query directly.
        
        On error, returns empty results and logs the error.
        """
        chat_params = state["chat_params"]
        
        try:
            # Determine which query to use based on whether query rewriting was performed
            query_text = state.get("rewritten_query") or chat_params.original_user_query
            filters = state.get("filters") or []
            
            # Validate query text
            if not query_text or not query_text.strip():
                logger.warning("Empty query text in document retrieval, using original query")
                query_text = chat_params.original_user_query
            
            is_advanced = state.get("rewritten_query") is not None
            
            results = await self.searcher.search_and_embed(
                query_text,
                top=chat_params.top,
                enable_vector_search=chat_params.enable_vector_search,
                enable_text_search=chat_params.enable_text_search,
                filters=filters if is_advanced else None,  # Only use filters in advanced mode
            )
            
            # Validate results
            if not results:
                logger.warning(f"No documents retrieved for query: {query_text}")
            
            thought_title = (
                "Document Retrieval (LangGraph - Advanced Mode)"
                if is_advanced
                else "Document Retrieval (LangGraph - Simple Mode)"
            )
            thought = ThoughtStep(
                title=thought_title,
                description=query_text,
                props={
                    "top": chat_params.top,
                    "vector_search": chat_params.enable_vector_search,
                    "text_search": chat_params.enable_text_search,
                    "filters": filters if is_advanced else None,
                    "results_count": len(results),
                    "mode": "advanced" if is_advanced else "simple",
                },
            )
            
            return {
                "search_results": results,
                "thoughts": [thought],
            }
        except Exception as e:
            logger.error(f"Error in document retrieval node: {e}", exc_info=True)
            error_thought = ThoughtStep(
                title="Document Retrieval (LangGraph - Error)",
                description=f"Document retrieval failed: {str(e)}",
                props={
                    "error": str(e),
                    "results_count": 0,
                },
            )
            return {
                "search_results": [],
                "thoughts": [error_thought],
            }
    
    async def _context_assembly_node(self, state: RAGState) -> dict[str, Any]:
        """
        Node 3: Context Assembly
        
        Assemble the contextual messages for the LLM by combining the user query,
        chat history, and retrieved documents.
        
        On error, creates messages without sources.
        """
        chat_params = state["chat_params"]
        results = state.get("search_results", [])
        
        try:
            sources_content = [
                f"[{item.id}]:{item.to_str_for_rag()}\n\n" for item in results
            ]
            content = "\n".join(sources_content)
            
            # Build contextual messages with sources (or without if no results)
            if content.strip():
                user_content_with_sources = f"{chat_params.original_user_query}\n\nSources:\n{content}"
            else:
                logger.warning("No sources available for context assembly")
                user_content_with_sources = chat_params.original_user_query
            
            contextual_messages: list[ChatCompletionMessageParam] = build_messages(
                model=self.chat_model,
                system_prompt=chat_params.prompt_template,
                new_user_content=user_content_with_sources,
                past_messages=chat_params.past_messages,
                max_tokens=self.chat_token_limit,
                fallback_to_default=True,
            )
            
            thought = ThoughtStep(
                title="Context Assembly (LangGraph)",
                description=[result.to_dict() for result in results] if results else [],
                props={
                    "documents_count": len(results),
                    "sources_length": len(content),
                },
            )
            
            return {
                "contextual_messages": contextual_messages,
                "thoughts": [thought],
            }
        except Exception as e:
            logger.error(f"Error in context assembly node: {e}", exc_info=True)
            try:
                fallback_messages: list[ChatCompletionMessageParam] = build_messages(
                    model=self.chat_model,
                    system_prompt=chat_params.prompt_template,
                    new_user_content=chat_params.original_user_query,
                    past_messages=chat_params.past_messages,
                    max_tokens=self.chat_token_limit,
                    fallback_to_default=True,
                )
                error_thought = ThoughtStep(
                    title="Context Assembly (LangGraph - Error)",
                    description=f"Context assembly failed: {str(e)}",
                    props={
                        "error": str(e),
                        "fallback": True,
                        "documents_count": len(results) if results else 0,
                    },
                )
                return {
                    "contextual_messages": fallback_messages,
                    "thoughts": [error_thought],
                }
            except Exception as fallback_error:
                logger.error(f"Fallback context assembly also failed: {fallback_error}", exc_info=True)
                error_thought = ThoughtStep(
                    title="Context Assembly (LangGraph - Critical Error)",
                    description=f"Context assembly and fallback both failed: {str(e)}; {str(fallback_error)}",
                    props={
                        "error": str(e),
                        "fallback_error": str(fallback_error),
                        "critical": True,
                    },
                )
                return {
                    "contextual_messages": [],
                    "thoughts": [error_thought],
                    "error": f"Context assembly failed: {str(e)}",
                }
    
    async def prepare_context(
        self,
        chat_params: ChatParams,
    ) -> tuple[
        list[ChatCompletionMessageParam], list[DocumentProtocol], list[ThoughtStep]
    ]:
        """
        Run the LangGraph workflow to prepare context for answer generation.
        
        This method maintains compatibility with the base RAGChatBase interface.
        Uses chat_params.use_advanced_flow to determine which graph to build.
        
        Raises:
            Exception: If the graph execution fails critically.
        """
        try:
            use_advanced = chat_params.use_advanced_flow
            graph = self._build_graph(use_advanced)
            initial_state = self._create_initial_state(chat_params)
            final_state = await graph.ainvoke(initial_state)
            
            # Validate final state
            contextual_messages = final_state.get("contextual_messages", [])
            search_results = final_state.get("search_results", [])
            thoughts = final_state.get("thoughts", [])
            
            # Check for errors in state
            if final_state.get("error"):
                logger.warning(f"Graph execution completed with error: {final_state['error']}")
            
            # Ensure we have at least minimal contextual messages
            if not contextual_messages:
                logger.warning("No contextual messages generated, creating fallback")
                contextual_messages = build_messages(
                    model=self.chat_model,
                    system_prompt=chat_params.prompt_template,
                    new_user_content=chat_params.original_user_query,
                    past_messages=chat_params.past_messages,
                    max_tokens=self.chat_token_limit,
                    fallback_to_default=True,
                )
            
            return (
                contextual_messages,
                search_results,
                thoughts,
            )
        except Exception as e:
            logger.error(f"Critical error in prepare_context: {e}", exc_info=True)
            fallback_messages = build_messages(
                model=self.chat_model,
                system_prompt=chat_params.prompt_template or self.answer_prompt_template,
                new_user_content=chat_params.original_user_query,
                past_messages=chat_params.past_messages,
                max_tokens=self.chat_token_limit,
                fallback_to_default=True,
            )
            error_thought = ThoughtStep(
                title="Graph Execution Error",
                description=f"Failed to prepare context: {str(e)}",
                props={"error": str(e), "critical": True},
            )
            return (
                fallback_messages,
                [],
                [error_thought],
            )
    
    async def answer(
        self,
        chat_params: ChatParams,
        contextual_messages: list[ChatCompletionMessageParam],
        results: list[DocumentProtocol],
        earlier_thoughts: list[ThoughtStep],
    ) -> RetrievalResponse:
        """Generate a non-streaming answer using the prepared context."""
        try:
            if not contextual_messages:
                raise ValueError("No contextual messages provided for answer generation")
            
            chat_completion_response: ChatCompletion = (
                await self.openai_chat_client.chat.completions.create(
                    model=self.chat_deployment if self.chat_deployment else self.chat_model,
                    messages=contextual_messages,
                    temperature=chat_params.temperature,
                    max_tokens=chat_params.response_token_limit,
                    n=1,
                    stream=False,
                    seed=chat_params.seed,
                )
            )
            
            # Validate response
            if not chat_completion_response.choices or not chat_completion_response.choices[0].message.content:
                raise ValueError("Empty response from chat completion")
            
            return RetrievalResponse(
                message=Message(
                    content=str(chat_completion_response.choices[0].message.content),
                    role=AIChatRoles.ASSISTANT,
                ),
                context=RAGContext(
                    data_points={item.id: item.to_dict() for item in results},
                    thoughts=earlier_thoughts
                    + [
                        ThoughtStep(
                            title="Answer Generation",
                            description=contextual_messages,
                            props=(
                                {
                                    "model": self.chat_model,
                                    "deployment": self.chat_deployment,
                                }
                                if self.chat_deployment
                                else {"model": self.chat_model}
                            ),
                        ),
                    ],
                ),
            )
        except Exception as e:
            logger.error(f"Error in answer generation: {e}", exc_info=True)
            error_thought = ThoughtStep(
                title="Answer Generation Error",
                description=f"Failed to generate answer: {str(e)}",
                props={"error": str(e)},
            )
            return RetrievalResponse(
                message=Message(
                    content=f"I apologize, but I encountered an error while generating a response: {str(e)}",
                    role=AIChatRoles.ASSISTANT,
                ),
                context=RAGContext(
                    data_points={item.id: item.to_dict() for item in results},
                    thoughts=earlier_thoughts + [error_thought],
                ),
            )
    
    async def answer_stream(
        self,
        chat_params: ChatParams,
        contextual_messages: list[ChatCompletionMessageParam],
        results: list[DocumentProtocol],
        earlier_thoughts: list[ThoughtStep],
    ) -> AsyncGenerator[RetrievalResponseDelta, None]:
        """Generate a streaming answer using the prepared context."""
        try:
            if not contextual_messages:
                raise ValueError("No contextual messages provided for answer generation")
            
            chat_completion_async_stream = await self.openai_chat_client.chat.completions.create(
                model=self.chat_deployment if self.chat_deployment else self.chat_model,
                messages=contextual_messages,
                temperature=chat_params.temperature,
                max_tokens=chat_params.response_token_limit,
                n=1,
                stream=True,
            )
            
            yield RetrievalResponseDelta(
                context=RAGContext(
                    data_points={item.id: item.to_dict() for item in results},
                    thoughts=earlier_thoughts
                    + [
                        ThoughtStep(
                            title="Answer Generation (Streaming)",
                            description=contextual_messages,
                            props=(
                                {
                                    "model": self.chat_model,
                                    "deployment": self.chat_deployment,
                                }
                                if self.chat_deployment
                                else {"model": self.chat_model}
                            ),
                        ),
                    ],
                ),
            )
            
            async for response_chunk in chat_completion_async_stream:
                if response_chunk.choices and response_chunk.choices[0].delta.content:
                    yield RetrievalResponseDelta(
                        delta=Message(
                            content=str(response_chunk.choices[0].delta.content),
                            role=AIChatRoles.ASSISTANT,
                        )
                    )
        except Exception as e:
            logger.error(f"Error in answer_stream generation: {e}", exc_info=True)
            error_thought = ThoughtStep(
                title="Answer Generation Error (Streaming)",
                description=f"Failed to generate streaming answer: {str(e)}",
                props={"error": str(e)},
            )
            yield RetrievalResponseDelta(
                context=RAGContext(
                    data_points={item.id: item.to_dict() for item in results},
                    thoughts=earlier_thoughts + [error_thought],
                ),
            )
            yield RetrievalResponseDelta(
                delta=Message(
                    content=f"I apologize, but I encountered an error while generating a response: {str(e)}",
                    role=AIChatRoles.ASSISTANT,
                )
            )

