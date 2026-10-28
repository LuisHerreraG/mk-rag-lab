"""Azure clients — one place that knows how to talk to the two services.

Two providers, two resources, two clients:
  Microsoft.CognitiveServices  →  Azure OpenAI (embeddings + chat)
  Microsoft.Search             →  Azure AI Search (index, vector + keyword)
"""

from __future__ import annotations

from functools import lru_cache

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from openai import AzureOpenAI

from .config import Settings


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings.load()


@lru_cache(maxsize=1)
def openai_client() -> AzureOpenAI:
    s = settings()
    return AzureOpenAI(
        azure_endpoint=s.openai_endpoint,
        api_key=s.openai_key,
        api_version=s.openai_api_version,
    )


@lru_cache(maxsize=1)
def index_client() -> SearchIndexClient:
    s = settings()
    return SearchIndexClient(
        endpoint=s.search_endpoint, credential=AzureKeyCredential(s.search_key)
    )


@lru_cache(maxsize=1)
def search_client(index_name: str | None = None) -> SearchClient:
    s = settings()
    return SearchClient(
        endpoint=s.search_endpoint,
        index_name=index_name or s.index_name,
        credential=AzureKeyCredential(s.search_key),
    )


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch. Used by both ingest and query — one code path, one shape."""
    s = settings()
    response = openai_client().embeddings.create(
        model=s.embed_deployment, input=texts
    )
    return [item.embedding for item in response.data]


def chat(messages: list[dict[str, str]], *, temperature: float | None = None) -> str:
    s = settings()
    kwargs: dict = {"model": s.chat_deployment, "messages": messages}
    if temperature is not None:
        kwargs["temperature"] = temperature
    response = openai_client().chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""
