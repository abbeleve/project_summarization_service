# main.py
import os
import tempfile
import uuid
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from typing import Optional
from ML_pipeline import AudioRecognition

app = FastAPI(title="Audio Transcription & Diarization Service")

# Глобальный инстанс
recognizer: Optional[AudioRecognition] = None

base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

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
    noise_sup_bool: str = Form('false'),
):
    print(file)
    if not recognizer:
        raise HTTPException(500, "Model not initialized")
    print('trans1')
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.mp3', '.wav', '.mp4', '.ogg']:
        raise HTTPException(400, f"Unsupported file format: {ext}")
    print('trans2')
    allowed_transcribe_libs = {"gigaam", "whisper"}
    allowed_diarize_libs = {"pyannote"}
    
    if transcribe_lib not in allowed_transcribe_libs:
        raise HTTPException(400, f"Unsupported transcribe_lib. Use: {allowed_transcribe_libs}")
    print('trans3')
    if diarize_lib not in allowed_diarize_libs:
        raise HTTPException(400, f"Unsupported diarize_lib. Use: {allowed_diarize_libs}")
    print('trans4')
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, f"{uuid.uuid4()}{ext}")
    try:
        print('trans5')
        with open(input_path, "wb") as f:
            f.write(await file.read())
        print('trans6')
        noise_sup_bool = noise_sup_bool.lower() in ("true", "yes", "1", "on")
        print('trans7')
        result = recognizer.run_diarization_transcription_pipeline(
            input_audio_path=input_path,
            diarization_lib=diarize_lib,
            transcribe_lib=transcribe_lib,
            diarization_model=diarization_model,
            transcribe_model=transcribe_model,
            noise_sup_bool=noise_sup_bool,
        )
        print(result)
        return {"transcript": result}

    except Exception as e:
        print(str(e))
        raise HTTPException(500, f"Processing failed: {str(e)}")

    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/summarize")
async def summarize(
    input_text: str = Form(None),
    llm_model: str = Form("arcee-ai/trinity-mini:free"),
):  
    global base_url
    if not recognizer:
        raise HTTPException(500, "Model not initialized")
    if not input_text:
        raise HTTPException(400, "'input_text' must be provided")
    allowed_models = {"arcee-ai/trinity-mini:free"}
    if llm_model not in allowed_models:
        raise HTTPException(400, f"Unsupported llm_backend. Use: {allowed_models}")
    
    try:
        summary = recognizer.summarize_with_openai(text=input_text, model=llm_model, base_url=base_url)
        return {"summary": summary}

    except Exception as e:
        raise HTTPException(500, f"Summarization failed: {str(e)}") from e

@app.post("/classify_meeting_type")
async def classify_meeting_type(
    input_text: str = Form(None),
    llm_model: str = Form("arcee-ai/trinity-mini:free"),
):
    global base_url
    if not recognizer:
        raise HTTPException(500, "Model not initialized")
    if not input_text:
        raise HTTPException(400, "'input_text = text' must be provided")
    allowed_models = {"arcee-ai/trinity-mini:free"}
    if llm_model not in allowed_models:
        raise HTTPException(400, f"Unsupported llm_backend. Use: {allowed_models}")
    try:
        meeting_type = recognizer.classify_meeting_type_with_openai(text=input_text,
                                                                model=llm_model, 
                                                                base_url=base_url)
        return {"meeting_type": meeting_type}
    except Exception as e:
        raise HTTPException(500, f"Meeting type classification failed: {str(e)}") from e

#Пока что синхронные функции
def _summarize(input_text: str, llm_model: str, base_url: str): #Просто функции, а не эндпоинты использующиеся для вызова из эндпоинта llm_pipeline
    if not recognizer:
        raise RuntimeError("Model not initialized")
    if not input_text:
        raise HTTPException(400, "'input_text' must be provided")
    allowed_models = {"arcee-ai/trinity-mini:free"}
    if llm_model not in allowed_models:
        raise HTTPException(400, f"Unsupported llm_backend. Use: {allowed_models}")
    
    try:
        summary = recognizer.summarize_with_openai(text=input_text, model=llm_model, base_url=base_url)
        return {"summary": summary}

    except Exception as e:
        raise HTTPException(500, f"Summarization failed: {str(e)}") from e

def _classify_meeting_type(input_text: str, llm_model: str, base_url: str):
    if not recognizer:
        raise RuntimeError("Model not initialized")
    if not input_text:
        raise HTTPException(400, "'input_text = text' must be provided")
    allowed_models = {"arcee-ai/trinity-mini:free"}
    if llm_model not in allowed_models:
        raise HTTPException(400, f"Unsupported llm_backend. Use: {allowed_models}")
    try:
        meeting_type = recognizer.classify_meeting_type_with_openai(text=input_text,
                                                                model=llm_model, 
                                                                base_url=base_url)
        return meeting_type
    except Exception as e:
        raise HTTPException(500, f"Meeting type classification failed: {str(e)}") from e

@app.post("/llm_pipeline")
async def llm_pipeline(
    input_text: str = Form(...),
    llm_model: str = Form("arcee-ai/trinity-mini:free"),
    summarization_usage: bool = Form(True),
    classification_usage: bool = Form(True),
):
    print(llm_model)
    global base_url
    print(input_text)
    base_url = base_url.strip()
    if summarization_usage: # ! Не делаем параллельные запросы иначе free версия модели упадет
        summary = _summarize(input_text=input_text, llm_model=llm_model, base_url=base_url)
    if classification_usage:
        meeting_type = _classify_meeting_type(input_text=input_text, llm_model=llm_model, base_url=base_url)
    if meeting_type:
        summary["summary"]["meeting_type"] = meeting_type
    return summary
    
@app.post("/ask")
async def question(request: Request):
    if not recognizer:
        raise HTTPException(500, "Model not initialized")

    try:
        body = await request.json()
        text = body.get("text")
        question = body.get("question")
        llm_model = body.get("llm_model", "openai/gpt-oss-20b:free")
    except Exception as e:
        raise ValueError("Invalid JSON") from e
    global base_url
    if not text:
        raise HTTPException(400, "'text' must be provided and non-empty")
    if not question or not question.strip():
        raise HTTPException(400, "'question' must be provided and non-empty")
    allowed_models = {"openai/gpt-oss-20b:free"}
    if llm_model not in allowed_models:
        raise HTTPException(400, f"Unsupported model. Use: {allowed_models}")

    base_url = base_url.strip()

    try:
        answer = recognizer.questions_with_openai(
            text=text,
            question=question,
            model=llm_model,
            base_url=base_url
        )

        return {"answer": answer}
    except Exception as e:
        raise HTTPException(500, f"LLM request failed: {str(e)}")