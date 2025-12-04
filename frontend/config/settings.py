# Конфигурационные параметры приложения
API_URL = "http://api:8000"

SUPPORTED_FORMATS = ['wav', 'mp3', 'm4a', 'flac', 'ogg']


# Модели транскрибации (для ML сервиса)
TRANSCRIBE_MODELS = [
    "v3_ctc"
]

# Библиотеки для транскрибации
TRANSCRIBE_LIBS = [
    "gigaam"
]

# Модели диаризации
DIARIZATION_MODELS = [
    "pyannote/speaker-diarization-community-1"
]

# Библиотеки для диаризации
DIARIZE_LIBS = [
    "pyannote"
]

# Модели для суммаризации (LLM)
LLM_MODELS = [
    "openai/gpt-oss-20b",
]
