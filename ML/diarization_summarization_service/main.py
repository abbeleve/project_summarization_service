# main.py
import os
import tempfile
import uuid
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from typing import Optional
from ML_pipeline import AudioRecognition

app = FastAPI(title="Audio Transcription & Diarization Service")

# Глобальный инстанс
recognizer: Optional[AudioRecognition] = None

@app.on_event("startup")
async def startup_event():
    global recognizer
    print("Loading AudioRecognition model...")
    recognizer = AudioRecognition()
    print("Model loaded.")

@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    transcribe_model: str = Form("v3_ctc"),
    diarization_model: str = Form("pyannote/speaker-diarization-community-1"),
    diarize_lib: str = Form("pyannote"),
    transcribe_lib: str = Form("gigaam"),
):
    if not recognizer:
        raise HTTPException(500, "Model not initialized")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.mp3', '.wav', '.mp4', '.ogg']:
        raise HTTPException(400, f"Unsupported file format: {ext}")

    allowed_transcribe_libs = {"gigaam", "whisper"}
    allowed_diarize_libs = {"pyannote"}

    if transcribe_lib not in allowed_transcribe_libs:
        raise HTTPException(400, f"Unsupported transcribe_lib. Use: {allowed_transcribe_libs}")
    if diarize_lib not in allowed_diarize_libs:
        raise HTTPException(400, f"Unsupported diarize_lib. Use: {allowed_diarize_libs}")

    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, f"{uuid.uuid4()}{ext}")

    try:
        with open(input_path, "wb") as f:
            f.write(await file.read())

        result = recognizer.run_diarization_transcription_pipeline(
            input_audio_path=input_path,
            diarization_lib=diarize_lib,
            transcribe_lib=transcribe_lib,
            diarization_model=diarization_model,
            transcribe_model=transcribe_model
        )
        print(result)
        return {"transcript": result}

    except Exception as e:
        raise HTTPException(500, f"Processing failed: {str(e)}")

    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/summarize")
async def summarize(
    text: Optional[str] = Form(None),
    llm_model: str = Form("openai/gpt-oss-20b"),
    base_url: str = Form("https://openrouter.ai/api/v1"),
    task_choice: str = Form("summarization"),
):
    if not recognizer:
        raise HTTPException(500, "Model not initialized")
    
    if not text:
        raise HTTPException(400, "'text' must be provided")
    
    allowed_models = {"openai/gpt-oss-20b"}
    if llm_model not in allowed_models:
        raise HTTPException(400, f"Unsupported llm_backend. Use: {allowed_models}")
    
    input_text = text
    temp_file_path = None
        
    if not input_text or not input_text.strip():
        raise HTTPException(400, "Input text is empty")
    
    try:
        print('here?')
        print(llm_model, base_url)
        summary = recognizer.summarize_with_openai(text=input_text, model=llm_model, base_url=base_url, task_choice=task_choice)
        return {"summary": summary}

    except Exception as e:
        raise HTTPException(500, f"Summarization failed: {str(e)}")
    
@app.post("/question")
async def question(
    text: str = Form(None),
    question: str = Form(None),
    llm_model: str = Form("openai/gpt-oss-20b"),
    base_url: str = Form("https://openrouter.ai/api/v1")
):
    if not recognizer:
        raise HTTPException(500, "Model not initialized")
    
    if not text:
        raise HTTPException(400, "'text' must be provided")
    
    allowed_models = {"openai/gpt-oss-20b"}
    if llm_model not in allowed_models:
        raise HTTPException(400, f"Unsupported llm_backend. Use: {allowed_models}")
    
    input_text = text
        
    if not input_text or not input_text.strip():
        raise HTTPException(400, "Input text is empty")
    
    try:
        summary = recognizer.questions_with_openai(text=input_text, question=question, model=llm_model, base_url=base_url)
        return {"summary": summary}

    except Exception as e:
        raise HTTPException(500, f"Summarization failed: {str(e)}")