# main.py
import os
import tempfile
import json
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from faster_whisper import WhisperModel
from tqdm import tqdm
from faster_whisper.audio import decode_audio
import soundfile as sf

WHISPER_MODEL_PATH = os.getenv("WHISPER_MODEL_PATH", "./models/faster-whisper-large-v3")
SAMPLE_RATE = 16000

model = WhisperModel(WHISPER_MODEL_PATH, device="cuda", compute_type="float16")

app = FastAPI(title="Whisper Transcription Service", version="1.0")


class DiarizationItem(BaseModel):
    start: float
    stop: float
    speaker: str


class TranscribeRequest(BaseModel):
    diarization_results: List[Dict]

@app.post("/transcribe")
async def transcribe_endpoint(
    request: str = Form(...),
    audio: UploadFile = File(...)
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await audio.read())
        audio_path = tmp.name

    try:
        if not os.path.isfile(audio_path):
            raise HTTPException(status_code=400, detail="Audio file not saved")
        if os.path.getsize(audio_path) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")

        audio_waveform = decode_audio(audio_path)
        request_data = json.loads(request)
        diarization_results = request_data["diarization_results"]

        for index, timings in tqdm(enumerate(diarization_results)):
            start_sample = int(timings["start"] * SAMPLE_RATE)
            stop_sample = int(timings["stop"] * SAMPLE_RATE)
            audio_chunk = audio_waveform[start_sample:stop_sample]

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as chunk_file:
                
                sf.write(chunk_file.name, audio_chunk, SAMPLE_RATE)
                segments, _ = model.transcribe(chunk_file.name, beam_size=5, language="ru")
                transcribed_text = "".join(segment.text for segment in segments)
                diarization_results[index]["Text"] = transcribed_text
                os.unlink(chunk_file.name)

        return JSONResponse(content=diarization_results)

    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)