"""
Voice Profile API Router

Endpoints for managing user voice profiles via Qdrant:
- Enroll voice (extract embedding → store in Qdrant)
- Get/delete voice profile
- Identify speakers during pipeline
"""
import logging
from typing import Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Request, Form

from app.db_service.database import DataBaseManager
from app.voice.speaker_identification import extract_embedding_from_wav_bytes
from app.voice.qdrant_profiles import (
    upsert_voice_profile,
    get_voice_profile,
    delete_voice_profile as qdrant_delete_profile,
    list_all_profiles,
    search_speaker,
    get_profile_count,
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


# --- Pydantic schemas ---

class VoiceProfileResponse(BaseModel):
    has_profile: bool
    created_at: Optional[str] = None
    full_name: Optional[str] = None
    embedding_dim: Optional[int] = None


class SpeakerIdentifyBatchRequest(BaseModel):
    """Batch request: list of embeddings, one per speaker segment."""
    embeddings: List[List[float]]
    threshold: float = 0.6


class SpeakerIdentifySegment(BaseModel):
    """Identification result for one speaker segment."""
    index: int
    user_id: Optional[str] = None
    full_name: Optional[str] = None
    score: Optional[float] = None


class SpeakerIdentifyBatchResponse(BaseModel):
    segments: List[SpeakerIdentifySegment]


class EnrolledSpeaker(BaseModel):
    user_id: str
    full_name: str
    has_embedding: bool


class EnrolledSpeakersResponse(BaseModel):
    speakers: List[EnrolledSpeaker]
    count: int


# --- Dependencies ---

def get_db():
    db = DataBaseManager()
    try:
        yield db
    finally:
        pass


async def get_current_user(request: Request) -> Dict:
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    user = request.state.user
    if not user or not user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user data in token"
        )
    return user


async def get_current_user_optional(request: Request) -> Optional[Dict]:
    """Optional auth — used by pipeline-internal endpoints."""
    if hasattr(request.state, "user") and request.state.user:
        return request.state.user
    return None


# --- Endpoints ---

@router.post("/enroll", response_model=VoiceProfileResponse)
async def enroll_voice(
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user),
):
    """
    Enroll (create/update) voice profile for the current user.

    Accepts audio file (WAV, MP3, M4A — any format supported by pydub),
    extracts a 192-dim ECAPA-TDNN speaker embedding, and stores it in Qdrant.
    Recommended: 10-30 seconds of clean, uninterrupted speech.
    """
    user_id_str = current_user["user_id"]
    full_name = current_user.get("full_name", "")

    try:
        audio_bytes = await file.read()
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")

        wav_bytes = _convert_to_wav(audio_bytes, file.filename or "audio")
        embedding = extract_embedding_from_wav_bytes(wav_bytes)

        if embedding is None:
            raise HTTPException(
                status_code=422,
                detail="Failed to extract speaker embedding. Please record clear speech (10-30s)."
            )

        success = upsert_voice_profile(
            user_id=UUID(user_id_str),
            embedding=embedding,
            full_name=full_name,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save voice profile to Qdrant")

        # Re-fetch to get timestamps
        profile = get_voice_profile(UUID(user_id_str))

        return VoiceProfileResponse(
            has_profile=True,
            created_at=profile["created_at"] if profile else None,
            full_name=full_name,
            embedding_dim=len(embedding),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice enrollment error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice enrollment failed: {str(e)}")


@router.get("/profile", response_model=VoiceProfileResponse)
async def get_voice_profile_endpoint(
    current_user: Dict = Depends(get_current_user),
):
    """Get the current user's voice profile status (no embedding returned)."""
    user_id = UUID(current_user["user_id"])
    profile = get_voice_profile(user_id)

    if not profile:
        return VoiceProfileResponse(has_profile=False)

    return VoiceProfileResponse(
        has_profile=True,
        created_at=profile.get("created_at"),
        full_name=profile.get("full_name"),
        embedding_dim=len(profile.get("embedding", [])),
    )


@router.delete("/profile", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice_profile_endpoint(
    current_user: Dict = Depends(get_current_user),
):
    """Delete the current user's voice profile from Qdrant."""
    user_id = UUID(current_user["user_id"])
    success = qdrant_delete_profile(user_id)

    if not success:
        raise HTTPException(status_code=404, detail="Voice profile not found")


@router.post("/identify-batch", response_model=SpeakerIdentifyBatchResponse)
async def identify_speakers_batch(
    request: SpeakerIdentifyBatchRequest,
):
    """
    Identify speakers from embeddings against all enrolled profiles.

    Designed for pipeline integration: pass a list of embeddings
    (one per diarized speaker segment) and get back matched identities.

    Threshold: 0.6 is a good default. Increase for stricter matching,
    decrease for more permissive matching.
    """
    try:
        segments: List[SpeakerIdentifySegment] = []

        for i, embedding in enumerate(request.embeddings):
            result = search_speaker(
                embedding=embedding,
                threshold=request.threshold,
            )

            if result:
                user_id, full_name, score = result
                segments.append(SpeakerIdentifySegment(
                    index=i,
                    user_id=str(user_id),
                    full_name=full_name,
                    score=score,
                ))
            else:
                segments.append(SpeakerIdentifySegment(index=i))

        return SpeakerIdentifyBatchResponse(segments=segments)

    except Exception as e:
        logger.error(f"Speaker identification error: {e}")
        raise HTTPException(status_code=500, detail=f"Identification failed: {str(e)}")


@router.get("/enrolled-speakers", response_model=EnrolledSpeakersResponse)
async def get_enrolled_speakers():
    """List all enrolled speakers (public info, no embeddings)."""
    profiles = list_all_profiles()
    speakers = [
        EnrolledSpeaker(
            user_id=str(p["user_id"]),
            full_name=p["full_name"],
            has_embedding=p["has_embedding"],
        )
        for p in profiles
    ]
    return EnrolledSpeakersResponse(speakers=speakers, count=len(speakers))


@router.get("/stats")
async def voice_stats():
    """Get voice enrollment statistics."""
    try:
        count = get_profile_count()
        return {"enrolled_count": count}
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {"enrolled_count": 0, "error": str(e)}


# --- Helper ---

def _convert_to_wav(audio_bytes: bytes, filename: str) -> bytes:
    """Convert any audio format to 16kHz mono WAV via pydub.
    
    Detects format from content (magic bytes) first, falls back to filename extension.
    Requires ffmpeg on the system for non-WAV formats (WebM, MP4, etc.).
    """
    import io as io_module

    # Detect format from magic bytes (more reliable than filename)
    def _guess_format(data: bytes):
        """Determine audio format from magic bytes. Returns format string or None."""
        if data.startswith(b'RIFF') and data[8:12] == b'WAVE':
            return 'wav'
        if data.startswith(b'\xff\xfb') or data.startswith(b'\xff\xf3') or data.startswith(b'\xff\xf2'):
            return 'mp3'
        if data.startswith(b'fLaC'):
            return 'flac'
        if data.startswith(b'OggS'):
            # Could be OGG or Opus-in-OGG or WebM
            return 'ogg'
        if data.startswith(b'\x1aE\xdf\xa3'):
            # Matroska/WebM container
            return 'webm'
        if data.startswith(b'ftyp'):
            return 'mp4'
        return None

    detected_format = _guess_format(audio_bytes)
    if detected_format:
        audio_format = detected_format
    else:
        # Fallback to filename extension
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else None
        fmt_map = {
            "wav": "wav", "mp3": "mp3", "m4a": "mp4",
            "flac": "flac", "ogg": "ogg", "webm": "webm",
            "mp4": "mp4",
        }
        audio_format = fmt_map.get(ext, "wav")

    try:
        from pydub import AudioSegment
        with io_module.BytesIO(audio_bytes) as buf:
            audio = AudioSegment.from_file(buf, format=audio_format)
    except ImportError:
        raise RuntimeError(
            "pydub is not installed. Install it: pip install pydub"
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "ffmpeg" in error_msg or "avconv" in error_msg:
            raise RuntimeError(
                "ffmpeg is required to convert audio formats. "
                "Install it:\n"
                "  Ubuntu/Debian: sudo apt-get install ffmpeg\n"
                "  Alpine (Docker): apk add ffmpeg\n"
                "  macOS: brew install ffmpeg"
            )
        raise RuntimeError(f"Audio conversion failed (format={audio_format}): {e}")

    audio = audio.set_frame_rate(16000).set_channels(1)

    with io_module.BytesIO() as out:
        audio.export(out, format="wav")
        return out.getvalue()