from sentence_transformers import SentenceTransformer
from src.data.clients.chroma_client import get_or_create_collection
from src.config.settings import get_settings
from src.observability.logging.logger import get_logger
from src.constants import CHROMA_COLLECTION_NAME

logger = get_logger(__name__)
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        settings = get_settings()
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def build_embedding_text(candidate: dict) -> str:
    parts = [
        " ".join(candidate.get("hard_skills", [])),
        " ".join(candidate.get("soft_skills", [])),
        candidate.get("summary", ""),
        " ".join(
            " ".join(e.get("technologies", []))
            for e in candidate.get("experience", [])
        ),
        " ".join(
            str(p) for p in candidate.get("projects", [])
        ),
    ]
    return " ".join(filter(None, parts))


async def embed_and_store(candidate_id: str, candidate: dict) -> None:
    text = build_embedding_text(candidate)
    if not text.strip():
        logger.warning("empty_embedding_text", candidate_id=candidate_id)
        return

    vector = get_model().encode(text).tolist()
    collection = await get_or_create_collection(CHROMA_COLLECTION_NAME)

    await collection.upsert(
        ids=[candidate_id],
        embeddings=[vector],
        metadatas=[{
            "name":     candidate.get("name", ""),
            "location": candidate.get("location", ""),
            "title":    candidate.get("title", ""),
        }],
    )
    logger.info("embedding_stored", candidate_id=candidate_id)