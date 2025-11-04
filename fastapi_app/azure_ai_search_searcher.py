from typing import Any, cast

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AsyncAzureOpenAI, AsyncOpenAI

from fastapi_app.azure_search_models import AzureSearchItem
from fastapi_app.embeddings import compute_text_embedding
from fastapi_app.protocols import DocumentProtocol


class AzureAISearchSearcher:
    """
    Azure AI Search retriever for documents with support for vector, full-text, and hybrid search.

    This class provides similar functionality to PostgresSearcher but uses Azure AI Search
    as the backend storage and retrieval system.
    """

    def __init__(
        self,
        search_client: SearchClient,
        openai_embed_client: AsyncOpenAI | AsyncAzureOpenAI,
        embed_deployment: str | None,  # Not needed for non-Azure OpenAI
        embed_model: str,
        embed_dimensions: int | None,
        embedding_field: str = "embedding",
        vector_search_profile: str = "default-vector-config",
    ):
        """
        Initialize the Azure AI Search searcher.

        Args:
            search_client: Azure Search client for the index
            openai_embed_client: OpenAI client for generating embeddings
            embed_deployment: Azure OpenAI deployment name (None for OpenAI)
            embed_model: Embedding model name
            embed_dimensions: Embedding dimensions
            embedding_field: Name of the vector field in the search index
            vector_search_profile: Vector search profile name in the index
        """
        self.search_client = search_client
        self.openai_embed_client = openai_embed_client
        self.embed_model = embed_model
        self.embed_deployment = embed_deployment
        self.embed_dimensions = embed_dimensions
        self.embedding_field = embedding_field
        self.vector_search_profile = vector_search_profile

    def build_filter_clause(self, filters: list[Any] | None) -> str:
        """
        Build OData filter expression for Azure AI Search.

        Args:
            filters: List of filter dictionaries with keys: column, comparison_operator, value

        Returns:
            OData filter string (empty string if no filters)
        """
        if filters is None or len(filters) == 0:
            return ""

        filter_clauses: list[str] = []
        for filter_item in filters:
            column = filter_item["column"]
            operator = filter_item["comparison_operator"]
            value = filter_item["value"]

            # Map SQL operators to OData operators
            operator_map = {
                "=": "eq",
                "!=": "ne",
                ">": "gt",
                ">=": "ge",
                "<": "lt",
                "<=": "le",
            }

            odata_operator = operator_map.get(operator, operator)

            # Format value based on type
            if isinstance(value, str):
                formatted_value = f"'{value}'"
            elif isinstance(value, bool):
                formatted_value = str(value).lower()
            elif value is None:
                formatted_value = "null"
            else:
                formatted_value = str(value)

            # Build OData expression
            if odata_operator in ["eq", "ne", "gt", "ge", "lt", "le"]:
                filter_clauses.append(f"{column} {odata_operator} {formatted_value}")
            else:
                # For custom operators, use them directly
                filter_clauses.append(f"{column} {operator} {formatted_value}")

        return " and ".join(filter_clauses)

    async def search(
        self,
        query_text: str | None,
        query_vector: list[float],
        top: int = 5,
        filters: list[Any] | None = None,
    ) -> list[DocumentProtocol]:
        """
        Search documents using vector, full-text, or hybrid search.

        Args:
            query_text: Text query for full-text search (None to disable)
            query_vector: Vector embedding for vector search (empty list to disable)
            top: Number of results to return
            filters: List of filter conditions

        Returns:
            List of documents matching the search criteria (implementing DocumentProtocol)
        """
        filter_clause = self.build_filter_clause(filters)

        # Determine search mode
        has_vector = len(query_vector) > 0
        has_text = query_text is not None and len(query_text.strip()) > 0

        if not has_vector and not has_text:
            raise ValueError("Both query text and query vector are empty")

        # Prepare vector query if applicable
        vector_queries = []
        if has_vector:
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=20,  # Retrieve top 20 for RRF
                fields=self.embedding_field,
            )
            # Set exhaustive KNN for better accuracy
            vector_query.exhaustive = True
            vector_queries.append(vector_query)

        # Perform search
        search_kwargs: dict[str, Any] = {
            "top": top,
            "select": ["chunk_id", "parent_id", "chunk", "title", "text_vector"],
        }

        if filter_clause:
            search_kwargs["filter"] = filter_clause

        if has_vector:
            search_kwargs["vector_queries"] = vector_queries

        # Configure search text
        if has_text:
            search_kwargs["search_text"] = query_text
        else:
            # For vector-only search, use empty search text
            search_kwargs["search_text"] = None

        # Perform the search
        results = self.search_client.search(**search_kwargs)

        # Convert results to AzureSearchItem objects
        items = []
        for result in results:
            # Create AzureSearchItem object from search result
            # Note: Azure AI Search returns results as dictionaries
            item = AzureSearchItem(
                chunk_id=result.get("chunk_id", ""),
                parent_id=result.get("parent_id", ""),
                chunk=result.get("chunk", ""),
                title=result.get("title", ""),
                text_vector=result.get("text_vector"),
            )
            items.append(item)

        return cast(list[DocumentProtocol], items)

    async def search_and_embed(
        self,
        query_text: str | None = None,
        top: int = 5,
        enable_vector_search: bool = False,
        enable_text_search: bool = False,
        filters: list[Any] | None = None,
    ) -> list[DocumentProtocol]:
        """
        Search rows by query text. Optionally converts the query text to a vector.

        Args:
            query_text: Text query string
            top: Number of results to return
            enable_vector_search: Whether to perform vector similarity search
            enable_text_search: Whether to perform full-text search
            filters: List of filter conditions

        Returns:
            List of documents matching the search criteria (implementing DocumentProtocol)
        """
        vector: list[float] = []

        if enable_vector_search and query_text is not None:
            # Generate embedding for the query text
            vector = await compute_text_embedding(
                query_text,
                self.openai_embed_client,
                self.embed_model,
                self.embed_deployment,
                self.embed_dimensions,
            )

        if not enable_text_search:
            query_text = None

        return await self.search(query_text, vector, top, filters)


def create_search_client(
    endpoint: str,
    index_name: str,
    api_key: str | None = None,
    credential: Any | None = None,
) -> SearchClient:
    """
    Create an Azure AI Search client.

    Args:
        endpoint: Azure AI Search service endpoint URL
        index_name: Name of the search index
        api_key: API key for authentication (alternative to credential)
        credential: Azure credential object (alternative to api_key)

    Returns:
        Configured SearchClient instance
    """
    if api_key:
        credential = AzureKeyCredential(api_key)
    elif credential is None:
        raise ValueError("Either api_key or credential must be provided")

    return SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=credential,
    )
