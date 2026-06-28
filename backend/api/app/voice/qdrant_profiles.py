"""
Voice Profile Manager — Qdrant-based storage for speaker embeddings.

Uses the existing Qdrant instance for vector storage and similarity search.
Collection: voice_profiles
Vector config: 192-dim, Cosine distance (ECAPA-TDNN output dimension)
"""
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse

logger = logging.getLogger(__name__)

# Singleton client
_client: Optional[QdrantClient] = None
COLLECTION_NAME = "voice_profiles"
VECTOR_DIM = 192  # ECAPA-TDNN produces 192-dim embeddings


def _get_client() -> QdrantClient:
    """Get or create the Qdrant client singleton."""
    global _client
    if _client is None:
        host = os.getenv("QDRANT_HOST", "qdrant")
        port = int(os.getenv("QDRANT_PORT", 6333))
        _client = QdrantClient(
            host=host,
            port=port,
            check_compatibility=False,  # совместимость client 1.16 ↔ server 1.13
        )
        _ensure_collection(_client)
    return _client


def _ensure_collection(client: QdrantClient):
    """Create the voice_profiles collection if it doesn't exist."""
    try:
        collections = client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)
        if not exists:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=qdrant_models.VectorParams(
                    size=VECTOR_DIM,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection '{COLLECTION_NAME}'")
    except UnexpectedResponse as e:
        logger.warning(f"Qdrant collection check failed: {e}")


def upsert_voice_profile(
    user_id: UUID,
    embedding: List[float],
    full_name: str,
) -> bool:
    """
    Create or update a voice profile for a user.

    Removes any existing point for this user, then inserts a new one.
    """
    client = _get_client()
    point_id = str(user_id)  # Use user_id as the point ID (idempotent)

    try:
        # Upsert via re-point: delete existing, insert new
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                qdrant_models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "user_id": str(user_id),
                        "full_name": full_name,
                        "created_at": datetime.utcnow().isoformat(),
                    },
                )
            ],
        )
        logger.info(f"Voice profile upserted for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to upsert voice profile for {user_id}: {e}")
        return False


def get_voice_profile(user_id: UUID) -> Optional[Dict[str, Any]]:
    """Retrieve a single user's voice profile from Qdrant."""
    client = _get_client()
    point_id = str(user_id)

    try:
        result = client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[point_id],
            with_payload=True,
            with_vectors=True,
        )
        if result:
            point = result[0]
            return {
                "user_id": user_id,
                "full_name": point.payload.get("full_name", ""),
                "embedding": point.vector if isinstance(point.vector, list) else point.vector.tolist(),
                "created_at": point.payload.get("created_at", ""),
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get voice profile for {user_id}: {e}")
        return None


def delete_voice_profile(user_id: UUID) -> bool:
    """Delete a user's voice profile."""
    client = _get_client()
    point_id = str(user_id)

    try:
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=qdrant_models.PointIdsList(
                points=[point_id],
            ),
        )
        logger.info(f"Voice profile deleted for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete voice profile for {user_id}: {e}")
        return False


def list_all_profiles() -> List[Dict[str, Any]]:
    """
    List all enrolled voice profiles (without full embeddings).
    Used for pipeline pre-loading and admin views.
    """
    client = _get_client()

    try:
        result = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=1000,
            with_payload=True,
            with_vectors=False,
        )
        points = result[0]
        return [
            {
                "user_id": UUID(p.payload["user_id"]),
                "full_name": p.payload.get("full_name", ""),
                "has_embedding": True,
            }
            for p in points
        ]
    except Exception as e:
        logger.error(f"Failed to list voice profiles: {e}")
        return []


def search_speaker(
    embedding: List[float],
    threshold: float = 0.5,
    top_k: int = 1,
) -> Optional[Tuple[UUID, str, float]]:
    """
    Search for the best matching speaker from enrolled profiles.

    Args:
        embedding: Query embedding vector (192-dim)
        threshold: Minimum cosine similarity threshold
        top_k: Number of top results to consider

    Returns:
        Tuple of (user_id, full_name, score) if best match exceeds threshold, else None
    """
    client = _get_client()

    try:
        result = client.query_points(
            collection_name=COLLECTION_NAME,
            query=embedding,
            limit=top_k,
            with_payload=True,
            score_threshold=threshold,
        )

        if result.points:
            best = result.points[0]
            return (
                UUID(best.payload["user_id"]),
                best.payload.get("full_name", ""),
                best.score,
            )
        return None
    except Exception as e:
        logger.error(f"Speaker search failed: {e}")
        return None


def get_profile_count() -> int:
    """Get the total number of enrolled voice profiles."""
    client = _get_client()
    try:
        collection_info = client.get_collection(COLLECTION_NAME)
        return collection_info.points_count or 0
    except Exception:
        return 0