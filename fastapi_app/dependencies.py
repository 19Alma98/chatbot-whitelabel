import logging
import os
from collections.abc import AsyncGenerator
from typing import Annotated, cast

import azure.identity
from fastapi import Depends, Request
from openai import AsyncAzureOpenAI, AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from fastapi_app.postgres_searcher import PostgresSearcher
from fastapi_app.azure_ai_search_searcher import AzureAISearchSearcher
from fastapi_app.protocols import SearcherProtocol

logger = logging.getLogger("ragapp")


class OpenAIClient(BaseModel):
    """
    OpenAI client
    """

    client: AsyncOpenAI | AsyncAzureOpenAI
    model_config = {"arbitrary_types_allowed": True}


class SearcherClient(BaseModel):
    """
    Searcher client
    """

    searcher: SearcherProtocol
    model_config = {"arbitrary_types_allowed": True}


class FastAPIAppContext(BaseModel):
    """
    Context for the FastAPI app
    """

    openai_chat_model: str
    openai_embed_model: str
    openai_embed_dimensions: int | None
    openai_chat_deployment: str | None
    openai_embed_deployment: str | None
    embedding_column: str
    vector_store: str  # "PGVECTOR" or "AZURE_AI_SEARCH"

    # Azure AI Search specific settings
    azure_search_endpoint: str | None = None
    azure_search_index: str | None = None
    azure_search_api_key: str | None = None


async def common_parameters() -> FastAPIAppContext:
    """
    Get the common parameters for the FastAPI app
    Use the pattern of `os.getenv("VAR_NAME") or "default_value"` to avoid empty string values
    """
    OPENAI_EMBED_HOST = os.getenv("OPENAI_EMBED_HOST")
    OPENAI_CHAT_HOST = os.getenv("OPENAI_CHAT_HOST")

    # Vector Store configuration
    vector_store = os.getenv("VECTOR_STORE") or "PGVECTOR"
    logger.info(f"Vector store: {vector_store}")
    azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    azure_search_index = os.getenv("AZURE_SEARCH_INDEX")
    azure_search_api_key = os.getenv("AZURE_SEARCH_API_KEY")

    if OPENAI_EMBED_HOST == "azure":
        openai_embed_deployment = (
            os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT") or "text-embedding-ada-002"
        )
        openai_embed_model = (
            os.getenv("AZURE_OPENAI_EMBED_MODEL") or "text-embedding-ada-002"
        )
        openai_embed_dimensions = int(
            os.getenv("AZURE_OPENAI_EMBED_DIMENSIONS") or 1536
        )
        embedding_column = (
            os.getenv("AZURE_OPENAI_EMBEDDING_COLUMN") or "embedding_ada002"
        )
    elif OPENAI_EMBED_HOST == "ollama":
        openai_embed_deployment = None
        openai_embed_model = os.getenv("OLLAMA_EMBED_MODEL") or "nomic-embed-text"
        openai_embed_dimensions = None
        embedding_column = os.getenv("OLLAMA_EMBEDDING_COLUMN") or "embedding_nomic"
    else:
        openai_embed_deployment = None
        openai_embed_model = (
            os.getenv("OPENAICOM_EMBED_MODEL") or "text-embedding-ada-002"
        )
        openai_embed_dimensions = int(os.getenv("OPENAICOM_EMBED_DIMENSIONS", 1536))
        embedding_column = os.getenv("OPENAICOM_EMBEDDING_COLUMN") or "embedding_ada002"
    if OPENAI_CHAT_HOST == "azure":
        openai_chat_deployment = (
            os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT") or "gpt-4o-mini"
        )
        openai_chat_model = os.getenv("AZURE_OPENAI_CHAT_MODEL") or "gpt-4o-mini"
    elif OPENAI_CHAT_HOST == "ollama":
        openai_chat_deployment = None
        openai_chat_model = os.getenv("OLLAMA_CHAT_MODEL") or "phi3:3.8b"
        openai_embed_model = os.getenv("OLLAMA_EMBED_MODEL") or "nomic-embed-text"
    else:
        openai_chat_deployment = None
        openai_chat_model = os.getenv("OPENAICOM_CHAT_MODEL") or "gpt-3.5-turbo"
    return FastAPIAppContext(
        openai_chat_model=openai_chat_model,
        openai_embed_model=openai_embed_model,
        openai_embed_dimensions=openai_embed_dimensions,
        openai_chat_deployment=openai_chat_deployment,
        openai_embed_deployment=openai_embed_deployment,
        embedding_column=embedding_column,
        vector_store=vector_store,
        azure_search_endpoint=azure_search_endpoint,
        azure_search_index=azure_search_index,
        azure_search_api_key=azure_search_api_key,
    )


async def get_azure_credential() -> (
    azure.identity.AzureDeveloperCliCredential
    | azure.identity.ManagedIdentityCredential
):
    azure_credential: (
        azure.identity.AzureDeveloperCliCredential
        | azure.identity.ManagedIdentityCredential
    )
    try:
        if client_id := os.getenv("APP_IDENTITY_ID"):
            # Authenticate using a user-assigned managed identity on Azure
            # See web.bicep for value of APP_IDENTITY_ID
            logger.info(
                "Using managed identity for client ID %s",
                client_id,
            )
            azure_credential = azure.identity.ManagedIdentityCredential(
                client_id=client_id
            )
        else:
            if tenant_id := os.getenv("AZURE_TENANT_ID"):
                logger.info(
                    "Authenticating to Azure using Azure Developer CLI Credential for tenant %s",
                    tenant_id,
                )
                azure_credential = azure.identity.AzureDeveloperCliCredential(
                    tenant_id=tenant_id, process_timeout=60
                )
            else:
                logger.info(
                    "Authenticating to Azure using Azure Developer CLI Credential"
                )
                azure_credential = azure.identity.AzureDeveloperCliCredential(
                    process_timeout=60
                )
        return azure_credential
    except Exception as e:
        logger.warning("Failed to authenticate to Azure: %s", e)
        raise e


async def create_async_sessionmaker(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Get the agent database"""
    return async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_async_sessionmaker(
    request: Request,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    yield request.state.sessionmaker


async def get_context(
    request: Request,
) -> FastAPIAppContext:
    return cast(FastAPIAppContext, request.state.context)


async def get_async_db_session(
    sessionmaker: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_async_sessionmaker)
    ],
) -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker() as session:
        yield session


async def get_openai_chat_client(
    request: Request,
) -> OpenAIClient:
    """Get the OpenAI chat client"""
    return OpenAIClient(client=request.state.chat_client)


async def get_openai_embed_client(
    request: Request,
) -> OpenAIClient:
    """Get the OpenAI embed client"""
    return OpenAIClient(client=request.state.embed_client)


async def get_searcher(
    request: Request, db_session: Annotated[AsyncSession, Depends(get_async_db_session)]
) -> SearcherClient:
    """
    Factory function to create the appropriate searcher based on VECTOR_STORE env variable.

    Returns:
        SearcherProtocol: Either PostgresSearcher or AzureAISearchSearcher
    """
    context = request.state.context
    embed_client = request.state.embed_client
    logger.info(f"Creating searcher for vector store: {context.vector_store}")
    if context.vector_store == "AZURE_AI_SEARCH":
        # Import here to avoid circular dependencies
        from fastapi_app.azure_ai_search_searcher import create_search_client

        if not context.azure_search_endpoint:
            raise ValueError(
                "AZURE_SEARCH_ENDPOINT environment variable is required for Azure AI Search"
            )
        if not context.azure_search_index:
            raise ValueError(
                "AZURE_SEARCH_INDEX environment variable is required for Azure AI Search"
            )

        if context.azure_search_api_key:
            search_client = create_search_client(
                endpoint=context.azure_search_endpoint,
                index_name=context.azure_search_index,
                api_key=context.azure_search_api_key,
            )
        else:
            # Use Azure credential (managed identity or Azure CLI)
            azure_credential = await get_azure_credential()
            search_client = create_search_client(
                endpoint=context.azure_search_endpoint,
                index_name=context.azure_search_index or "documents",
                credential=azure_credential,
            )

        return SearcherClient(
            searcher=cast(
                SearcherProtocol,
                AzureAISearchSearcher(
                    search_client=search_client,
                    openai_embed_client=embed_client,
                    embed_deployment=context.openai_embed_deployment,
                    embed_model=context.openai_embed_model,
                    embed_dimensions=context.openai_embed_dimensions,
                    embedding_field="text_vector",  # Default field name for Azure AI Search. TODO: Make this configurable.
                ),
            )
        )

    elif context.vector_store == "PGVECTOR":
        if db_session is None:
            raise ValueError("Database session is required for PGVECTOR")

        return SearcherClient(
            searcher=cast(
                SearcherProtocol,
                PostgresSearcher(
                    db_session=db_session,
                    openai_embed_client=embed_client.client,
                    embed_deployment=context.openai_embed_deployment,
                    embed_model=context.openai_embed_model,
                    embed_dimensions=context.openai_embed_dimensions,
                    embedding_column=context.embedding_column,
                ),
            )
        )

    else:
        raise ValueError(
            f"Unknown VECTOR_STORE: {context.vector_store}. "
            "Supported values are: PGVECTOR, AZURE_AI_SEARCH"
        )


CommonDeps = Annotated[FastAPIAppContext, Depends(get_context)]
DBSession = Annotated[AsyncSession, Depends(get_async_db_session)]
ChatClient = Annotated[OpenAIClient, Depends(get_openai_chat_client)]
EmbeddingsClient = Annotated[OpenAIClient, Depends(get_openai_embed_client)]
VectorDBClient = Annotated[SearcherClient, Depends(get_searcher)]
