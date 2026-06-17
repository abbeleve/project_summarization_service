"""
Full-audio transcription client.

Transcribes an entire audio file in one pass (not segment-by-segment),
by delegating to the dedicated GigaAM or Whisper microservice.

Returns the raw concatenated text — no diarization, no segment splitting.
"""
import json
import logging
from typing import Optional

import requests

from config import settings

logger = logging.getLogger(__name__)


class FullTranscriber:
    """
    Transcribes an entire audio file and returns the raw text.

    Two backends are available:
      - gigaam  → onnx-gigaam:8056/transcribe_full
      - whisper → audio-ml-whisper:8054/transcribe_full
    """

    def __init__(self):
        self.gigaam_url: str = settings.gigaam_onnx_full_url
        self.whisper_url: str = settings.whisper_full_url
        self.gigaam_timeout: int = settings.gigaam_onnx_timeout_sec
        self.whisper_timeout: int = settings.whisper_timeout_sec

    def transcribe_full(
        self,
        audio_path: str,
        transcribe_lib: str = "gigaam",
    ) -> str:
        """
        Transcribe the entire audio file in one pass.

        Args:
            audio_path: Path to the WAV audio file.
            transcribe_lib: "gigaam" or "whisper".

        Returns:
            Full transcription text as a single string.

        Raises:
            ValueError: If transcribe_lib is unsupported.
            RuntimeError: If the remote service fails.
        """
        if transcribe_lib == "gigaam":
            return self._transcribe_gigaam(audio_path)
        elif transcribe_lib == "whisper":
            return self._transcribe_whisper(audio_path)
        else:
            raise ValueError(f"Unsupported transcribe_lib: {transcribe_lib}")

    # ------------------------------------------------------------------
    # GigaAM ONNX full transcription
    # ------------------------------------------------------------------

    def _transcribe_gigaam(self, audio_path: str) -> str:
        url = self.gigaam_url
        logger.info(f"Full-audio GigaAM transcription via {url}")

        try:
            with open(audio_path, "rb") as f:
                files = {"audio": (audio_path, f, "audio/wav")}
                resp = requests.post(url, files=files, timeout=self.gigaam_timeout)

            if resp.status_code != 200:
                raise RuntimeError(
                    f"GigaAM full service error {resp.status_code}: {resp.text}"
                )

            result = resp.json()
            text = result.get("text", "")
            logger.info(f"GigaAM full transcription done: {len(text)} chars")
            return text

        except requests.Timeout:
            raise RuntimeError(
                f"GigaAM full service timeout after {self.gigaam_timeout}s"
            )
        except requests.ConnectionError as e:
            raise RuntimeError(
                f"Cannot connect to GigaAM full service at {url}: {e}"
            )

    # ------------------------------------------------------------------
    # Whisper full transcription
    # ------------------------------------------------------------------

    def _transcribe_whisper(self, audio_path: str) -> str:
        url = self.whisper_url
        logger.info(f"Full-audio Whisper transcription via {url}")

        try:
            with open(audio_path, "rb") as f:
                files = {"audio": (audio_path, f, "audio/wav")}
                resp = requests.post(url, files=files, timeout=self.whisper_timeout)

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Whisper full service error {resp.status_code}: {resp.text}"
                )

            result = resp.json()
            text = result.get("text", "")
            logger.info(f"Whisper full transcription done: {len(text)} chars")
            return text

        except requests.Timeout:
            raise RuntimeError(
                f"Whisper full service timeout after {self.whisper_timeout}s"
            )
        except requests.ConnectionError as e:
            raise RuntimeError(
                f"Cannot connect to Whisper full service at {url}: {e}"
            )
