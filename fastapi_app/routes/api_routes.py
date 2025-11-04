import json
import logging
from collections.abc import AsyncGenerator
from fastapi import UploadFile, File, Depends

import fastapi
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from openai import APIError
from sqlalchemy import select, text

from fastapi_app.api_models import (
    ChatRequest,
    ConversationHistoryResponse,
    ConversationMessagePublic,
    ErrorResponse,
    ItemPublic,
    ItemWithDistance,
    RetrievalResponse,
    RetrievalResponseDelta,
)
from fastapi_app.conversation_service import ConversationService
from fastapi_app.dependencies import ChatClient, CommonDeps, DBSession, VectorDBClient, get_async_sessionmaker
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from typing import Annotated
from fastapi_app.postgres_models import Item
from fastapi_app.rag_advanced import AdvancedRAGChat
from fastapi_app.rag_simple import SimpleRAGChat
from fastapi_app.pdf_processor import PDFProcessor

router = fastapi.APIRouter()
logger = logging.getLogger("ragapp")

ERROR_FILTER = {
    "error": "Your message contains content that was flagged by the content filter."
}


async def format_as_ndjson(
    r: AsyncGenerator[RetrievalResponseDelta, None],
) -> AsyncGenerator[str, None]:
    """
    Format the response as NDJSON
    """
    try:
        async for event in r:
            yield event.model_dump_json() + "\n"
    except Exception as error:
        if isinstance(error, APIError) and error.code == "content_filter":
            yield json.dumps(ERROR_FILTER) + "\n"
        else:
            logging.exception("Exception while generating response stream: %s", error)
            yield json.dumps({"error": str(error)}, ensure_ascii=False) + "\n"


@router.get("/items/{id}", response_model=ItemPublic)
async def item_handler(database_session: DBSession, id: int) -> ItemPublic:
    """A simple API to get an item by ID."""
    item = (await database_session.scalars(select(Item).where(Item.id == id))).first()
    if not item:
        raise HTTPException(detail=f"Item with ID {id} not found.", status_code=404)
    return ItemPublic.model_validate(item.to_dict())


@router.get("/similar", response_model=list[ItemWithDistance])
async def similar_handler(
    context: CommonDeps, database_session: DBSession, id: int, n: int = 5
) -> list[ItemWithDistance]:
    """A similarity API to find items similar to items with given ID."""
    item = (await database_session.scalars(select(Item).where(Item.id == id))).first()
    if not item:
        raise HTTPException(detail=f"Item with ID {id} not found.", status_code=404)

    closest = (
        await database_session.execute(
            text(
                f"SELECT *, {context.embedding_column} <=> :embedding as DISTANCE FROM {Item.__tablename__} "
                "WHERE id <> :item_id ORDER BY distance LIMIT :n"
            ),
            {"embedding": item.embedding_ada002, "n": n, "item_id": id},
        )
    ).fetchall()

    items = [dict(row._mapping) for row in closest]
    return [ItemWithDistance.model_validate(item) for item in items]


@router.get("/search", response_model=list[ItemPublic])
async def search_handler(
    searcher: VectorDBClient,
    query: str,
    top: int = 5,
    enable_vector_search: bool = True,
    enable_text_search: bool = True,
) -> list[ItemPublic]:
    """A search API to find items based on a query."""
    results = await searcher.searcher.search_and_embed(
        query,
        top=top,
        enable_vector_search=enable_vector_search,
        enable_text_search=enable_text_search,
    )
    return [ItemPublic.model_validate(item.to_dict()) for item in results]


@router.post("/chat", response_model=RetrievalResponse | ErrorResponse)
async def chat_handler(
    context: CommonDeps,
    openai_chat: ChatClient,
    searcher: VectorDBClient,
    chat_request: ChatRequest,
    database_session: DBSession,
) -> RetrievalResponse | ErrorResponse:
    try:
        conversation_service = ConversationService(database_session)
        conversation_id = chat_request.conversation_id
        
        all_messages = []
        if conversation_id:
            history = await conversation_service.get_conversation_history(conversation_id)
            all_messages = [
                {"role": msg.message_role, "content": msg.message_content}
                for msg in history
            ]
            logger.info(f"Loaded {len(all_messages)} messages from conversation {conversation_id}")
        else:
            conversation_id = ConversationService.generate_conversation_id()
            logger.info(f"Generated new conversation ID: {conversation_id}")
        
        if chat_request.messages:
            new_user_message = chat_request.messages[-1]  # Get the last message (the new one)
            all_messages.append(new_user_message)
            await conversation_service.save_message(
                conversation_id=conversation_id,
                role=new_user_message["role"],
                content=str(new_user_message["content"]),
            )

        rag_flow: SimpleRAGChat | AdvancedRAGChat
        if chat_request.context.overrides.use_advanced_flow:
            rag_flow = AdvancedRAGChat(
                searcher=searcher,
                openai_chat_client=openai_chat.client,
                chat_model=context.openai_chat_model,
                chat_deployment=context.openai_chat_deployment,
            )
        else:
            rag_flow = SimpleRAGChat(
                searcher=searcher,
                openai_chat_client=openai_chat.client,
                chat_model=context.openai_chat_model,
                chat_deployment=context.openai_chat_deployment,
            )

        chat_params = rag_flow.get_params(
            all_messages, chat_request.context.overrides
        )
        contextual_messages, results, thoughts = await rag_flow.prepare_context(
            chat_params
        )
        response = await rag_flow.answer(
            chat_params=chat_params,
            contextual_messages=contextual_messages,
            results=results,
            earlier_thoughts=thoughts,
        )
        
        # Save the assistant's response
        await conversation_service.save_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response.message.content,
        )
        
        return response
    except Exception as e:
        if isinstance(e, APIError) and e.code == "content_filter":
            return ErrorResponse(error=ERROR_FILTER["error"])
        else:
            return ErrorResponse(error=str(e))


@router.post("/chat/stream")
async def chat_stream_handler(
    context: CommonDeps,
    openai_chat: ChatClient,
    searcher: VectorDBClient,
    chat_request: ChatRequest,
    database_session: DBSession,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_async_sessionmaker)],
) -> StreamingResponse:
    conversation_service = ConversationService(database_session)
    
    conversation_id = chat_request.conversation_id
    
    # Load existing conversation history if conversation_id is provided
    all_messages = []
    if conversation_id:
        # Get conversation history from database
        history = await conversation_service.get_conversation_history(conversation_id)
        all_messages = [
            {"role": msg.message_role, "content": msg.message_content}
            for msg in history
        ]
        logger.info(f"Loaded {len(all_messages)} messages from conversation {conversation_id}")
    else:
        # Generate new conversation ID if not provided
        conversation_id = ConversationService.generate_conversation_id()
        logger.info(f"Generated new conversation ID: {conversation_id}")
    
    # Add only the new user message from the request
    if chat_request.messages:
        new_user_message = chat_request.messages[-1]  # Get the last message (the new one)
        all_messages.append(new_user_message)
    
    rag_flow: SimpleRAGChat | AdvancedRAGChat
    if chat_request.context.overrides.use_advanced_flow:
        rag_flow = AdvancedRAGChat(
            searcher=searcher,
            openai_chat_client=openai_chat.client,
            chat_model=context.openai_chat_model,
            chat_deployment=context.openai_chat_deployment,
        )
    else:
        rag_flow = SimpleRAGChat(
            searcher=searcher,
            openai_chat_client=openai_chat.client,
            chat_model=context.openai_chat_model,
            chat_deployment=context.openai_chat_deployment,
        )

    chat_params = rag_flow.get_params(
        all_messages, chat_request.context.overrides
    )

    # Intentionally do this before we stream down a response, to avoid using database connections during stream
    # See https://github.com/tiangolo/fastapi/discussions/11321
    try:
        if chat_request.messages:
            new_user_message = chat_request.messages[-1]
            await conversation_service.save_message(
                conversation_id=conversation_id,
                role=new_user_message["role"],
                content=str(new_user_message["content"]),
            )
        
        contextual_messages, results, thoughts = await rag_flow.prepare_context(
            chat_params
        )
        
        async def save_streamed_response(
            stream: AsyncGenerator[RetrievalResponseDelta, None],
            session_maker: async_sessionmaker[AsyncSession],
            conv_id: str,
        ) -> AsyncGenerator[RetrievalResponseDelta, None]:
            """Wrapper to collect and save the streamed assistant response."""
            full_response = ""
            async for event in stream:
                if event.delta and event.delta.content:
                    full_response += event.delta.content
                yield event
            
            # Save the complete assistant response after streaming
            # Create a new session that's independent of the request lifecycle
            if full_response:
                async with session_maker() as session:
                    conv_service = ConversationService(session)
                    await conv_service.save_message(
                        conversation_id=conv_id,
                        role="assistant",
                        content=full_response,
                    )
        
        result = rag_flow.answer_stream(
            chat_params=chat_params,
            contextual_messages=contextual_messages,
            results=results,
            earlier_thoughts=thoughts,
        )

        wrapped_result = save_streamed_response(result, sessionmaker, conversation_id)
        
    except Exception as e:
        if isinstance(e, APIError) and e.code == "content_filter":
            return StreamingResponse(
                content=json.dumps(ERROR_FILTER) + "\n",
                media_type="application/x-ndjson",
            )
    return StreamingResponse(
        content=format_as_ndjson(wrapped_result), media_type="application/x-ndjson"
    )


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)) -> dict[str, str]:
    """Upload a PDF file, process it, and store its embeddings in the database."""
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    try:
        processor = PDFProcessor()
        processed_chunks = await processor.process_pdf(file)
        logger.info(f"Saving {len(processed_chunks)} chunks")
        await processor.save_to_database(processed_chunks)
        return {
            "message": f"Successfully processed {len(processed_chunks)} chunks from {file.filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    database_session: DBSession,
    conversation_id: str,
    limit: int | None = None,
) -> ConversationHistoryResponse:
    """
    Retrieve conversation history for a given conversation ID.
    
    Args:
        conversation_id: The ID of the conversation
        limit: Optional limit on the number of messages to retrieve
    """
    conversation_service = ConversationService(database_session)
    messages = await conversation_service.get_conversation_history(
        conversation_id=conversation_id,
        limit=limit,
    )
    
    if not messages:
        raise HTTPException(
            status_code=404,
            detail=f"No conversation found with ID {conversation_id}",
        )
    
    return ConversationHistoryResponse(
        conversation_id=conversation_id,
        messages=[
            ConversationMessagePublic.model_validate(msg.to_dict())
            for msg in messages
        ],
    )


@router.get("/conversations")
async def list_conversations(
    database_session: DBSession,
    limit: int = 50,
) -> list[dict[str, str]]:
    """
    Get a list of all conversations with their most recent message timestamp.
    
    Args:
        limit: Maximum number of conversations to return (default: 50)
    """
    conversation_service = ConversationService(database_session)
    conversations = await conversation_service.get_conversation_list(limit=limit)
    return conversations


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    database_session: DBSession,
    conversation_id: str,
) -> dict[str, str | int]:
    """
    Delete all messages from a conversation.
    
    Args:
        conversation_id: The ID of the conversation to delete
    """
    conversation_service = ConversationService(database_session)
    deleted_count = await conversation_service.delete_conversation(conversation_id)
    
    if deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No conversation found with ID {conversation_id}",
        )
    
    return {
        "message": f"Deleted conversation {conversation_id}",
        "deleted_messages": deleted_count,
    }
