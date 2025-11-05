import os
from typing import List, Dict, Any
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import (
    CharacterTextSplitter,
)  # TODO: Use RecursiveTextSplkitter
from fastapi import UploadFile
import numpy as np
from .embeddings import compute_text_embedding
from .openai_clients import create_openai_embed_client
from .dependencies import common_parameters, get_azure_credential
from .postgres_models import Item
from sqlalchemy.ext.asyncio import async_sessionmaker
from .postgres_engine import create_postgres_engine_from_env
from sqlalchemy import select, text


class PDFProcessor:
    def __init__(self, chunk_size: int = 2500, chunk_overlap: int = 500):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = CharacterTextSplitter(
            separator="\n", chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

    async def process_pdf(self, file: UploadFile) -> List[Dict[str, Any]]:
        # Save the uploaded file temporarily
        temp_path = f"temp_{file.filename}"
        try:
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)

            # Load and split the PDF
            loader = PyPDFLoader(temp_path)
            docs = loader.load()
            splits = self.text_splitter.split_documents(docs)

            # Get embeddings for each chunk
            azure_credential = await get_azure_credential()
            openai_embed_client = await create_openai_embed_client(azure_credential)
            common_params = await common_parameters()

            # Determine embedding column based on environment
            OPENAI_EMBED_HOST = os.getenv("OPENAI_EMBED_HOST")
            if OPENAI_EMBED_HOST == "azure":
                embedding_column = os.getenv(
                    "AZURE_OPENAI_EMBEDDING_COLUMN", "embedding_ada002"
                )
            elif OPENAI_EMBED_HOST == "ollama":
                embedding_column = os.getenv(
                    "OLLAMA_EMBEDDING_COLUMN", "embedding_nomic"
                )
            else:
                embedding_column = os.getenv(
                    "OPENAICOM_EMBEDDING_COLUMN", "embedding_ada002"
                )

            # Process each chunk
            processed_chunks = []
            for i, doc in enumerate(splits):
                embedding = await compute_text_embedding(
                    doc.page_content,
                    openai_client=openai_embed_client,
                    embed_model=common_params.openai_embed_model,
                    embed_deployment=common_params.openai_embed_deployment,
                    embedding_dimensions=common_params.openai_embed_dimensions,
                )

                processed_chunks.append(
                    {
                        "id": i,
                        "file_name": file.filename,
                        "description": doc.page_content,
                        embedding_column: embedding,
                    }
                )

            return processed_chunks

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def save_to_database(self, processed_chunks: List[Dict[str, Any]]) -> None:
        azure_credential = await get_azure_credential()
        engine = await create_postgres_engine_from_env(azure_credential)

        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            async with session.begin():
                for chunk in processed_chunks:
                    #     item = Item(**chunk)
                    #     session.add(item)
                    # await session.commit()
                    table_name = Item.__tablename__
                    db_item = await session.execute(
                        select(Item).filter(Item.id == chunk["id"])
                    )
                    if db_item.scalars().first():
                        continue
                    attrs = {key: value for key, value in chunk.items()}
                    attrs["embedding_ada002"] = np.array(chunk["embedding_ada002"])
                    column_names = ", ".join(attrs.keys())
                    values = ", ".join([f":{key}" for key in attrs.keys()])
                    await session.execute(
                        text(
                            f"INSERT INTO {table_name} ({column_names}) VALUES ({values})"
                        ),
                        attrs,
                    )
