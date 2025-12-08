# Конфигурационные параметры приложения
API_URL = "http://api:8000"

SUPPORTED_FORMATS = ['wav', 'mp3', 'm4a', 'flac', 'ogg']

# Связка библиотек и моделей (библиотека: [список моделей])
TRANSCRIBE_CONFIG = {
    "gigaam": [
        "v3_ctc",
        "v3_rnnt", 
        "v3_e2e_ctc",
        "v3_ssl"
    ],
    "whisper": [
        "large-v3"
    ]
}

DIARIZATION_CONFIG = {
    "pyannote": [
        "pyannote/speaker-diarization-community-1",
        "pyannote/speaker-diarization-community-2"
    ]
}

# Модели для суммаризации (LLM)
LLM_MODELS = [
    "openai/gpt-oss-20b:free",
    "openai/gpt-oss-120b:free"
]

# Списки для обратной совместимости
TRANSCRIBE_LIBS = list(TRANSCRIBE_CONFIG.keys())
DIARIZE_LIBS = list(DIARIZATION_CONFIG.keys())

# Получить модели по библиотеке
def get_transcribe_models_by_lib(lib_name: str) -> list:
    """Получить список моделей для библиотеки транскрибации"""
    return TRANSCRIBE_CONFIG.get(lib_name, [])

def get_diarization_models_by_lib(lib_name: str) -> list:
    """Получить список моделей для библиотеки диаризации"""
    return DIARIZATION_CONFIG.get(lib_name, [])

# Получить библиотеку по модели
def get_lib_by_transcribe_model(model_name: str) -> str:
    """Получить библиотеку по названию модели транскрибации"""
    for lib, models in TRANSCRIBE_CONFIG.items():
        if model_name in models:
            return lib
    return "gigaam"  # значение по умолчанию

def get_lib_by_diarization_model(model_name: str) -> str:
    """Получить библиотеку по названию модели диаризации"""
    for lib, models in DIARIZATION_CONFIG.items():
        if model_name in models:
            return lib
    return "pyannote"  # значение по умолчанию