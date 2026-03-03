from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import Response
import os
import tempfile
import torch
import shutil
from denoise import denoise_file

app = FastAPI(title="Audio Denoiser", version="0.2")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "cuda_available": torch.cuda.is_available(),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_memory_total": f"{torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB" if torch.cuda.is_available() else None
    }

@app.post("/denoise")
async def denoise(file: UploadFile = File(...)):
    if not torch.cuda.is_available():
        print("WARNING: CUDA not available, falling back to CPU")

    # Проверка размера файла (макс 100 MB)
    file_content = await file.read()
    if len(file_content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 100 MB)")

    input_path = None
    output_path = None
    
    try:
        # Создаём временные файлы
        input_fd, input_path = tempfile.mkstemp(suffix=".wav")
        output_fd, output_path = tempfile.mkstemp(suffix="_clean.wav")
        
        # Закрываем файловые дескрипторы
        os.close(input_fd)
        os.close(output_fd)
        
        # Записываем входной файл
        with open(input_path, "wb") as f:
            f.write(file_content)

        # Запускаем шумоподавление
        denoise_file(input_path, output_path)

        if not os.path.exists(output_path):
            raise RuntimeError("Denoising completed but output file was not created")

        # Читаем результат и возвращаем как Response
        with open(output_path, "rb") as f:
            cleaned_audio = f.read()

        return Response(
            content=cleaned_audio,
            media_type="audio/wav",
            headers={
                "Content-Disposition": 'attachment; filename="cleaned_audio.wav"'
            }
        )

    except Exception as e:
        print(f"Error during denoising: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Denoising failed: {str(e)}")

    finally:
        # Очищаем временные файлы
        try:
            if input_path and os.path.exists(input_path):
                os.remove(input_path)
            if output_path and os.path.exists(output_path):
                os.remove(output_path)
        except Exception as e:
            print(f"Warning: Failed to cleanup temp files: {e}")
