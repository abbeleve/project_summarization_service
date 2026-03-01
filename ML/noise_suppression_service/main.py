from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import os
import tempfile
import torch
from denoise import denoise_file

app = FastAPI(title="Audio Denoiser", version="0.1")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "cuda_available": torch.cuda.is_available(),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_memory_total": f"{torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB" if torch.cuda.is_available() else None
    }

@app.post("/denoise", response_class=FileResponse)
async def denoise(file: UploadFile = File(...)):
    if not torch.cuda.is_available():
        print("WARNING: CUDA not available, falling back to CPU")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as inp:
        input_path = inp.name
        inp.write(await file.read())
        inp.flush()

    with tempfile.NamedTemporaryFile(delete=False, suffix="_clean.wav") as out:
        output_path = out.name
    try:
        denoise_file(input_path, output_path)

        if not os.path.exists(output_path):
            raise RuntimeError("Denoising completed but output file was not created")

        return FileResponse(output_path, media_type="audio/wav", filename="cleaned_audio.wav")

    except Exception as e:
        print(f"Error during denoising: {e}")
        raise HTTPException(status_code=500, detail=f"Denoising failed: {e}")

    finally:
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)