# client.py
import requests
import json
from typing import List, Dict, Any

def transcribe_with_whisper_service(
    diarization_results: List[Dict],
    input_audio_path: str,
    whisper_service_url: str = "http://audio-ml-whisper:8054/transcribe"
) -> List[Dict]:
    """
    Отправляет аудиофайл и сегменты диаризации на сервис транскрибации.
    
    Args:
        diarization_results: список словарей вида {"start": float, "stop": float, "speaker": str}
        input_audio_path: путь к локальному .wav/.mp3 файлу (должен быть доступен в клиентском контейнере)
        whisper_service_url: URL сервиса (по умолчанию — имя сервиса в Docker Compose)

    Returns:
        Список тех же сегментов, но с добавленным ключом "Text"
    """
    # Проверка входных данных
    if not diarization_results:
        raise ValueError("diarization_results is empty")
    if not input_audio_path or not input_audio_path.endswith(('.wav', '.mp3', '.flac', '.ogg')):
        raise ValueError("Invalid audio file path")

    with open(input_audio_path, "rb") as audio_file:
        print(audio_file)
        files = {
            "audio": (input_audio_path.split("/")[-1], audio_file, "audio/wav"),
            "request": (None, json.dumps({"diarization_results": diarization_results}), "application/json")
        }
        try:
            response = requests.post(whisper_service_url, files=files, timeout=300)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print("Response status:", response.status_code)
            print("Response body:", response.text)
            raise RuntimeError(f"Failed to transcribe via whisper service: {e}")