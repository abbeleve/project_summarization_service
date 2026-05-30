"""
Speaker Identification Module

Extracts speaker embeddings from audio using ECAPA-TDNN (SpeechBrain)
and matches against enrolled voice profiles using cosine similarity.
"""
import io
import os
import logging
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)

# Lazy-loaded model singleton
_model = None

# Model path: configurable via env var, defaults to project-relative path
SPEAKER_MODEL_PATH = os.getenv(
    "SPEAKER_MODEL_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "speaker_embedding")
)


def _get_model():
    """Lazy-load the ECAPA-TDNN speaker embedding model."""
    global _model
    if _model is None:
        try:
            from speechbrain.inference.speaker import SpeakerRecognition
            logger.info(f"Loading ECAPA-TDNN speaker embedding model from {SPEAKER_MODEL_PATH}...")

            # Create the directory if it doesn't exist
            os.makedirs(SPEAKER_MODEL_PATH, exist_ok=True)

            # Check if model already downloaded locally
            model_files = os.listdir(SPEAKER_MODEL_PATH)
            if model_files:
                logger.info(f"Found existing model files ({len(model_files)} files), loading from cache")

            _model = SpeakerRecognition.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=SPEAKER_MODEL_PATH,
                run_opts={"device": "cpu"}
            )
            logger.info("Speaker embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load speaker embedding model: {e}")
            raise
    return _model


def extract_embedding(audio_bytes: bytes, sample_rate: int = 16000) -> Optional[List[float]]:
    """
    Extract speaker embedding from raw audio bytes.

    Args:
        audio_bytes: Raw WAV audio bytes (16kHz mono recommended)
        sample_rate: Sample rate of the audio

    Returns:
        192-dimensional embedding vector as list of floats, or None on failure
    """
    try:
        import torch
        import torchaudio

        model = _get_model()

        # Load audio from bytes
        with io.BytesIO(audio_bytes) as buf:
            waveform, sr = torchaudio.load(buf)

        # Resample to 16kHz if needed
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(sr, 16000)
            waveform = resampler(waveform)
            sr = 16000

        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        # Extract embedding
        with torch.no_grad():
            embedding = model.encode_batch(waveform)

        # Convert to list of floats
        return embedding.squeeze().tolist()

    except Exception as e:
        logger.error(f"Error extracting speaker embedding: {e}")
        return None


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_np = np.array(a, dtype=np.float64)
    b_np = np.array(b, dtype=np.float64)
    dot = np.dot(a_np, b_np)
    norm = np.linalg.norm(a_np) * np.linalg.norm(b_np)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def match_embedding(
    embedding: List[float],
    known_profiles: List[Dict[str, Any]],
    threshold: float = 0.6
) -> Optional[Tuple[UUID, str, float]]:
    """
    Match an embedding against known voice profiles.

    Args:
        embedding: The query embedding vector
        known_profiles: List of dicts with 'user_id', 'full_name', 'embedding' keys
        threshold: Minimum cosine similarity for a match

    Returns:
        Tuple of (user_id, full_name, score) if match found, None otherwise
    """
    best_match = None
    best_score = threshold

    for profile in known_profiles:
        profile_emb = profile.get("embedding")
        if not profile_emb:
            continue

        score = cosine_similarity(embedding, profile_emb)
        logger.debug(f"Similarity with {profile.get('full_name', '?')}: {score:.4f}")

        if score > best_score:
            best_score = score
            best_match = (
                profile["user_id"],
                profile["full_name"],
                score
            )

    if best_match:
        logger.info(f"Speaker matched: {best_match[1]} (score: {best_score:.4f})")
    else:
        logger.debug("No speaker match found above threshold")

    return best_match


def extract_embedding_from_wav_bytes(wav_bytes: bytes) -> Optional[List[float]]:
    """
    Extract speaker embedding from WAV audio bytes.
    
    Tries multiple audio loaders in order:
    1. torchaudio (native, supports WAV/FLAC/OGG)
    2. soundfile (fallback, supports WAV/FLAC/OGG natively)
    
    The input MUST be valid WAV audio (16kHz mono recommended).
    """
    try:
        import torch
        model = _get_model()

        waveform = None
        sr = None

        # Try torchaudio first
        try:
            import torchaudio
            import torchaudio.functional as F
            import io as io_module

            with io_module.BytesIO(wav_bytes) as buf:
                waveform, sr = torchaudio.load(buf)
        except Exception as e:
            logger.debug(f"torchaudio failed to load audio: {e}")
            waveform = None

        # Fallback to soundfile if torchaudio failed
        if waveform is None:
            try:
                import soundfile as sf
                import io as io_module
                import numpy as np

                with io_module.BytesIO(wav_bytes) as buf:
                    data, sr = sf.read(buf)
                # soundfile returns (samples, channels) for stereo, (samples,) for mono
                if data.ndim == 1:
                    waveform = torch.from_numpy(data).unsqueeze(0).float()
                else:
                    waveform = torch.from_numpy(data.T).float()
                    if waveform.shape[0] > 1:
                        waveform = torch.mean(waveform, dim=0, keepdim=True)
            except ImportError:
                raise RuntimeError(
                    "Neither torchaudio nor soundfile can read this audio. "
                    "Install soundfile: pip install soundfile"
                )
            except Exception as e:
                logger.error(f"soundfile also failed: {e}")
                raise RuntimeError(
                    f"Cannot read audio file. Ensure the file is a valid WAV format. "
                    f"If recording from browser, ensure ffmpeg is installed for WebM conversion. "
                    f"Error: {e}"
                )

        # Normalize to mono 16kHz
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        if sr != 16000:
            import torchaudio.functional as F
            waveform = F.resample(waveform, sr, 16000)

        # Normalize amplitude
        max_val = torch.max(torch.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val

        # Extract embedding
        with torch.no_grad():
            embedding = model.encode_batch(waveform)

        return embedding.squeeze().tolist()

    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Error extracting embedding from WAV: {e}")
        return None
