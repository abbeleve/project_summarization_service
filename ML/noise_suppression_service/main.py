from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import os
import tempfile
from denoise import denoise_file

app = FastAPI(title="Audio Denoiser", version="0.1")

@app.post("/denoise", response_class=FileResponse)
async def denoise(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as inp:
        input_path = inp.name
        inp.write(await file.read())

    output_path = tempfile.mktemp(suffix="_clean.wav")
    print(output_path)
    try:
        denoise_file(input_path, output_path)

        if not os.path.exists(output_path):
            raise RuntimeError("Denoising completed but output file was not created")

        return FileResponse(output_path, media_type="audio/wav", filename="clean.wav")

    except Exception as e:
        print(f"Error during denoising: {e}")
        raise HTTPException(status_code=500, detail=f"Denoising failed: {e}")

    finally:
        if os.path.exists(input_path):
            os.remove(input_path)