from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import os
import tempfile
import logging
from denoise import denoise_file, BATCH_DURATION_SEC

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Audio Denoiser", version="0.2")


def cleanup_file(path: str):
    """Фоновая очистка временного файла."""
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Удалён временный файл: {path}")
    except Exception as e:
        logger.error(f"Ошибка при удалении {path}: {e}")


@app.post("/denoise")
async def denoise(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    file_size_mb = file.size / (1024 * 1024) if file.size else "unknown"
    logger.info(f"Получен файл: {file.filename}, размер: {file_size_mb} MB")
    
    # Создаем временные файлы
    input_path = None
    output_path = None
    
    try:
        # Сохраняем входной файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as inp:
            input_path = inp.name
            inp.write(await file.read())

        output_path = tempfile.mktemp(suffix="_clean.wav")
        logger.info(f"Начало шумоподавления: {input_path} → {output_path}")
        
        # Шумоподавление
        denoise_file(input_path, output_path)

        if not os.path.exists(output_path):
            raise RuntimeError("Denoising completed but output file was not created")

        output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"Шумоподавление завершено, выходной файл: {output_size_mb:.2f} MB")

        # Добавляем задачу на очистку после отправки
        background_tasks.add_task(cleanup_file, output_path)
        
        # Возвращаем файл
        return FileResponse(
            output_path, 
            media_type="audio/wav", 
            filename="denoised_audio.wav"
        )

    except Exception as e:
        logger.error(f"Error during denoising: {e}")
        # Если ошибка - удаляем и выходной файл тоже
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
        raise HTTPException(status_code=500, detail=f"Denoising failed: {e}")
    finally:
        # Удаляем только входной файл
        if input_path and os.path.exists(input_path):
            os.remove(input_path)