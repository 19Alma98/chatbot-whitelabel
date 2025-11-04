from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DocumentProtocol(Protocol):
    """
    Protocol for document items returned from vector stores.

    All document models (PostgreSQL Item, Azure SearchItem, etc.) must implement
    this protocol to ensure compatibility with RAG implementations.
    """

    id: str | int

    def to_dict(self, include_embedding: bool = False) -> dict[str, Any]:
        """
        Convert the document to a dictionary representation.

        Args:
            include_embedding: Whether to include the embedding vector in the output

        Returns:
            Dictionary representation of the document
        """
        ...

    def to_str_for_rag(self) -> str:
        """
        Convert the document to a string format optimized for RAG context.

        Returns:
            Formatted string suitable for inclusion in RAG prompts
        """
        ...


@runtime_checkable
class SearcherProtocol(Protocol):
    """
    Protocol for vector store searchers.

    All searcher implementations (PostgresSearcher, AzureAISearchSearcher, etc.)
    must implement this protocol.
    """

    async def search_and_embed(
        self,
        query_text: str | None = None,
        top: int = 5,
        enable_vector_search: bool = False,
        enable_text_search: bool = False,
        filters: list[Any] | None = None,
    ) -> list[DocumentProtocol]:
        """
        Search for documents using text and/or vector search.

        Args:
            query_text: Text query string
            top: Number of results to return
            enable_vector_search: Whether to perform vector similarity search
            enable_text_search: Whether to perform full-text search
            filters: List of filter conditions

        Returns:
            List of documents matching the search criteria
        """
        ...
