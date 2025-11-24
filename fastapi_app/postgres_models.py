from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, String, Text, DateTime, ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB


# Define the models
class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    # Embeddings for different models:
    embedding_ada002: Mapped[Vector] = mapped_column(
        Vector(1536), nullable=True
    )  # ada-002

    def to_dict(self, include_embedding: bool = False) -> dict[str, Any]:
        model_dict = {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
        if include_embedding:
            model_dict["embedding_ada002"] = model_dict.get("embedding_ada002", [])
        else:
            del model_dict["embedding_ada002"]
        return model_dict

    def to_str_for_rag(self) -> str:
        return f"File name:{self.file_name} Description:{self.description}"

    def to_str_for_embedding(self) -> str:
        return f"File name:{self.file_name} Description: {self.description}"


class ConversationMemory(Base):
    __tablename__ = "conversation_memory"
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    message_role: Mapped[str] = mapped_column(String(50), nullable=False)
    message_content: Mapped[str] = mapped_column(Text, nullable=False)
    message_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # Debug columns for RAG flow data
    chat_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    contextual_messages: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB, nullable=True
    )
    document_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    thoughts: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": str(self.message_id),
            "conversation_id": self.conversation_id,
            "message_role": self.message_role,
            "message_content": self.message_content,
            "message_timestamp": self.message_timestamp.isoformat(),
            "chat_params": self.chat_params,
            "contextual_messages": self.contextual_messages,
            "document_ids": self.document_ids,
            "thoughts": self.thoughts,
        }


"""
**Define HNSW index to support vector similarity search**

We use the vector_cosine_ops access method (cosine distance)
 since it works for both normalized and non-normalized vector embeddings
If you know your embeddings are normalized,
 you can switch to inner product for potentially better performance.
The index operator should match the operator used in queries.
"""

table_name = Item.__tablename__

index_ada002 = Index(
    "hnsw_index_for_cosine_{table_name}_embedding_ada002",
    Item.embedding_ada002,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding_ada002": "vector_cosine_ops"},
)
