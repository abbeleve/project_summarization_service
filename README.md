🎙️ Meeting Insight — Автоматическая обработка встреч
Диаризация • Транскрибация • Суммаризация
Сервис для полного анализа аудиозаписей встреч: кто говорил, что сказал и главное — в чём суть? 

Python

FastAPI

Docker

Streamlit

License

📌 Описание
Meeting Insight — это полный пайплайн для автоматической обработки аудиозаписей совещаний:

Диаризация речи — определение, кто из участников говорил и когда (pyannote.audio).
Транскрибация — преобразование речи в текст с разбивкой по спикерам (faster-whisper).
Суммаризация — генерация краткого содержания с помощью современных LLM (например, через OpenRouter или GigaChat).
Сервис разработан с учётом сложной зависимости версий между ML-библиотеками — каждая стадия изолирована в отдельный Docker-контейнер, а взаимодействие между ними происходит через унифицированный FastAPI-бэкенд. Интерфейс для пользователей и аналитиков реализован на Streamlit.

🚀 Основные возможности
Поддержка аудиоформатов: WAV, MP3, OGG, MP4 (аудиодорожка).
Автоматическое определение числа спикеров.
Сохранение временных меток и привязка текста к говорящему.
Экспорт транскрипции в текстовый файл или JSON.
Краткое содержание встречи по запросу (настраиваемые промпты).
Готов к развёртыванию в Docker-окружении с GPU-ускорением.
📦 Стек технологий
Backend API
FastAPI
Диаризация
pyannote.audio
(Hugging Face)
Транскрибация
faster-whisper
(Whisper large-v3)
Суммаризация
LLM через OpenRouter / GigaChat API
Frontend / UI
Streamlit
Контейнеризация
Docker + Docker Compose
Аудиообработка
torchaudio
,
ffmpeg
Язык
Python 3.10+

🛠️ Быстрый старт
1. Клонируйте репозиторий
bash


1
2
git clone https://github.com/your-username/meeting-insight.git
cd meeting-insight
Важно: Убедитесь, что у вас установлены git, docker и docker-compose. 

2. Настройте переменные окружения
Создайте файл .env:

env


1
2
HF_TOKEN=your_huggingface_token
OPENROUTER_API_KEY=your_openrouter_key  # или GIGACHAT_API_KEY при использовании GigaChat
Токен Hugging Face требуется для загрузки модели диаризации. 

3. Соберите и запустите сервис
bash


1
docker-compose up --build
Это автоматически:

Соберёт образы diarize-service и transcribe-service
Запустит FastAPI-бэкенд на http://localhost:8000
Поднимет Streamlit-интерфейс на http://localhost:8501
🧪 Пример использования через API
Отправьте аудиофайл на обработку:

bash


1
2
3
4
5
6
curl -X POST "http://localhost:8000/process" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "audio=@./meeting.mp3" \
  -F "summarize=true" \
  -o result.json
Ответ содержит:

Диаризированный и транскрибированный текст
(Опционально) краткое содержание встречи
🖥️ Streamlit-интерфейс
Перейдите в браузере: http://localhost:8501

Загрузите аудиофайл
Посмотрите результаты в реальном времени
Скачайте транскрипцию или суммаризацию
📂 Структура проекта


1
2
3
4
5
6
7
8
9
meeting-insight/
├── backend/               # FastAPI-сервер
├── diarize/               # Docker-образ для диаризации
├── transcribe/            # Docker-образ для транскрибации
├── streamlit/             # Streamlit-фронтенд
├── shared/                # Общая директория для обмена файлами между контейнерами
├── docker-compose.yml
├── .env.example
└── README.md
⚠️ Известные ограничения
Зависимости: pyannote.audio >= 3.0 требует аргумент use_auth_token, а не token — учтено в коде.
GPU: Для ускорения рекомендуется наличие CUDA-совместимой видеокарты.
Аудио: Очень короткие реплики (<0.5 сек) могут фильтроваться как артефакты.
📄 Лицензия
Проект распространяется под лицензией MIT — см. файл LICENSE .
