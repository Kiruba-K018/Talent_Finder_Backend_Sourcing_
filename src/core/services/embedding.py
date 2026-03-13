from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from src.data.clients.chroma_client import get_chroma_client
from src.config.settings import get_settings

_ef = SentenceTransformerEmbeddingFunction(
    model_name=get_settings().embedding_model
)

async def get_or_create_collection():
    client = await get_chroma_client()
    return await client.get_or_create_collection(
        name=get_settings().chroma_collection,
        embedding_function=_ef,
        metadata={"hnsw:space": "cosine"},
    )

async def embed_and_store(candidate_id: str, candidate: dict) -> None:
    text = build_embedding_text(candidate)
    if not text.strip():
        return
    collection = await get_or_create_collection()
    await collection.upsert(
        ids=[candidate_id],
        documents=[text],        # chromadb embeds this automatically
        metadatas=[{
            "name":     candidate.get("name", ""),
            "location": candidate.get("location", ""),
            "title":    candidate.get("title", ""),
        }],
    )