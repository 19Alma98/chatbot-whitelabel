from typing import Any

from pydantic import BaseModel, Field


class AzureSearchItem(BaseModel):
    """
    Model representing a document/chunk from Azure AI Search.

    This model maps to the Azure AI Search index schema with fields:
    - chunk_id: Unique identifier for the chunk
    - parent_id: ID of the parent document
    - chunk: The text content of the chunk
    - title: Title of the document
    - text_vector: Embedding vector for semantic search
    """

    chunk_id: str = Field(..., description="Unique identifier for the chunk")
    parent_id: str = Field(..., description="ID of the parent document")
    chunk: str = Field(..., description="Text content of the chunk")
    title: str = Field(..., description="Title of the document")
    text_vector: list[float] | None = Field(
        default=None, description="Embedding vector for semantic search"
    )

    class Config:
        # Allow arbitrary types for compatibility
        arbitrary_types_allowed = True

    @property
    def id(self) -> str:
        """
        Property to satisfy DocumentProtocol requirement.
        Returns chunk_id as the document identifier.
        """
        return self.chunk_id

    def to_dict(self, include_embedding: bool = False) -> dict[str, Any]:
        """
        Convert the model to a dictionary.

        Args:
            include_embedding: Whether to include the text_vector in the output

        Returns:
            Dictionary representation of the model
        """
        if include_embedding:
            return self.model_dump()
        else:
            return self.model_dump(exclude={"text_vector"})

    def to_str_for_rag(self) -> str:
        """
        Convert to string format optimized for RAG (Retrieval Augmented Generation).

        Returns:
            Formatted string for RAG context
        """
        return f"Title: {self.title}\nContent: {self.chunk}"

    def to_str_for_embedding(self) -> str:
        """
        Convert to string format optimized for embedding generation.

        Returns:
            Formatted string for embedding
        """
        return f"Title: {self.title} Content: {self.chunk}"


class AzureSearchItemPublic(BaseModel):
    """
    Public API model for Azure Search items (without embeddings).
    """

    chunk_id: str
    parent_id: str
    chunk: str
    title: str


class AzureSearchItemWithScore(AzureSearchItemPublic):
    """
    Azure Search item with search score/relevance.
    """

    score: float = Field(..., description="Search relevance score")

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.score = round(self.score, 4)
