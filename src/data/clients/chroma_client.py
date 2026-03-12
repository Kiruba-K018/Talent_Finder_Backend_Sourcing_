import chromadb
from chromadb import AsyncHttpClient, Collection
from src.config.settings import get_settings

_client: chromadb.AsyncHttpClient | None = None


async def get_chroma_client() -> chromadb.AsyncHttpClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = await AsyncHttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
    return _client


async def get_or_create_collection(name: str) -> Collection:
    client = await get_chroma_client()
    return await client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )