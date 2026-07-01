# 🎙️ Meeting Insight — Автоматическая обработка встреч

> **Диаризация • Транскрибация • Суммаризация • RAG • Идентификация спикеров**
> Полный пайплайн для анализа аудиозаписей встреч: кто говорил, что сказал и в чём суть?

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-black?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📌 Описание

**Meeting Insight** — микросервисный пайплайн для полного цикла обработки встреч:

1. **Автоматический вход и запись** — бот на Playwright подключается к Zoom / Google Meet / Teams.
2. **Шумоподавление** — очистка аудиодорожки перед распознаванием (DeepFilterNet).
3. **Транскрибация** — распознавание речи в текст (Whisper large-v3 или GigaAM RNNT/CTC).
4. **Диаризация** — определение, кто и когда говорил (`pyannote.audio`).
5. **Forced Alignment** — покадровая привязка слов к временным меткам (GigaAM ONNX, встроенный RNN-T декодер).
6. **Идентификация спикеров** — сопоставление SPEAKER_XX с реальными людьми по голосовому отпечатку (ECAPA-TDNN + Qdrant).
7. **Суммаризация** — генерация краткого содержания через LLM (OpenRouter / GigaChat).
8. **RAG** — семантический поиск по транскриптам (гибридный dense + sparse, sentence-aware чанкинг).

Каждая стадия изолирована в собственный Docker-контейнер с GPU-ускорением. Фронтенд — React 19 + TypeScript.

---

## ⚡ Ключевые характеристики

| Метрика | Значение |
|---------|----------|
| ⏱ **Скорость обработки** | 1 час аудио → **5–6 минут** (WhisperX pipeline) |
| 🎯 **Точность транскрипции (русский)** | **WER ~3.5%** (GigaAM RNNT / Whisper large-v3) |
| 👥 **Разделение спикеров** | Автоматическое определение числа говорящих + **идентификация по голосовому отпечатку** (ECAPA-TDNN) |
| 📝 **Word-level таймстемпы** | Каждое слово привязано к таймкоду (GigaAM ONNX aligner) |
| 🤖 **LLM-аналитика** | Краткое содержание, ключевые тезисы, тип встречи, **структурированные задачи** для task-трекеров |
| 📊 **Экспорт** | TXT / JSON / интеграция с **Weeek CRM** |
| 🎨 **Интерфейс** | React 19 + Tailwind CSS 4 — тёмная тема, аудиоплеер с синхронизацией по таймкодам, RAG-чат, аннотации текста |

---

## 🚀 Основные возможности

- Автоматическое подключение к Zoom / Google Meet / Teams через Playwright-бота
- Поддержка загружаемых аудио: `WAV`, `MP3`, `OGG`, `MP4`, `WebM`, `FLAC`, `M4A`
- Автоматическое определение числа спикеров
- Временные метки с привязкой текста к говорящему (word-level alignment)
- Шумоподавление перед распознаванием (DeepFilterNet, батчи по 60 с)
- Два ASR-движка на выбор: Whisper large-v3 (мультиязычный) и GigaAM (русский)
- **Идентификация спикеров по голосу** — запись голоса в личном кабинете → автоматическое распознавание в транскриптах (ECAPA-TDNN, порог 0.5)
- Краткое содержание встречи (заголовок, summary, key points, тип, задачи)
- Гибридный RAG-поиск по истории транскриптов (dense + sparse, фильтры по дате/типу/спикеру)
- Аннотации текста с цветовым кодированием
- Интеграция с Weeek CRM (отправка извлечённых задач)
- JWT-аутентификация, управление пользователями (admin / user), личный кабинет
- Админ-панель: управление пользователями, аналитика использования
- Экспорт транскрипции в TXT / JSON
- Готов к развёртыванию в Docker-окружении с NVIDIA GPU

---

## 🚢 Развёртывание

### Системные требования

| Ресурс | Минимально | Рекомендуется |
|--------|-----------|---------------|
| **RAM** | 32 GB | 64 GB |
| **GPU VRAM** | 12 GB | 24 GB (NVIDIA A10G / RTX 4090 / A100) |
| **CPU** | 8 ядер | 16 ядер |
| **Диск** | 100 GB (SSD) | 200 GB (NVMe) |
| **Docker** | 24+ | 27+ |
| **NVIDIA Driver** | 545+ | 570+ |
| **OC** | Linux (Ubuntu 22.04+) | Linux (Ubuntu 24.04) |

---

### 1. Настройте окружение

```bash
git clone <repo-url>
cd meeting-insight
cp .env.example .env
```

Обязательные переменные `.env`:

| Переменная | По умолч. | Описание | Откуда взять |
|-----------|----------|----------|-------------|
| `HF_API_KEY` | — | Hugging Face токен | https://huggingface.co/settings/tokens (нужен доступ к `pyannote/speaker-diarization-community`) |
| `OPENAI_API_KEY` | — | Ключ LLM для суммаризации | OpenRouter / GigaChat / Gemini |
| `OPENAI_BASE_URL` | `https://openrouter.ai/api/v1` | Базовый URL LLM провайдера | OpenRouter / GigaChat / Gemini |
| `JWT_SECRET_KEY` | — | Секрет для JWT | `openssl rand -hex 32` |
| `POSTGRES_USER` | — | Пользователь PostgreSQL | Задайте любые |
| `POSTGRES_PASSWORD` | — | Пароль PostgreSQL | Задайте любые |
| `POSTGRES_DB` | — | Имя БД PostgreSQL | Задайте любые |
| `MINIO_ROOT_USER` | — | MinIO admin пользователь | Задайте любые |
| `MINIO_ROOT_PASSWORD` | — | MinIO admin пароль | Задайте любые |

---

### 2. Подготовьте ML-модели

Тяжёлые модели **монтируются через Docker volumes** — они НЕ встроены в образы.
Их нужно скачать до первого запуска.

```bash
mkdir -p ML/diarization_summarization_service/models/pyannote
mkdir -p ML/whisper_transcription_service/models/faster-whisper-large-v3
mkdir -p ML/whisper_transcription_service/models/faster-distil-whisper-large-v3-ru
mkdir -p ML/onnx_gigaam_service/models/gigaam_v3_e2e_rnnt
mkdir -p ML/onnx_gigaam_service/models/gigaam_v3_e2e_ctc
```

#### Pyannote (диаризация)

Требуется доступ на Hugging Face (принять лицензию https://huggingface.co/pyannote/speaker-diarization-community).

```bash
pip install huggingface-hub
huggingface-cli login --token $HF_API_KEY

huggingface-cli download pyannote/speaker-diarization-community \
  --local-dir ML/diarization_summarization_service/models/pyannote
```

#### Whisper (транскрибация)

```bash
# faster-whisper large-v3 — мультиязычный
huggingface-cli download phr0m/faster-whisper-large-v3 \
  --local-dir ML/whisper_transcription_service/models/faster-whisper-large-v3

# faster-distil-whisper large-v3-ru int8 — русский (опционально)
huggingface-cli download phr0m/faster-distil-whisper-large-v3-ru-int8 \
  --local-dir ML/whisper_transcription_service/models/faster-distil-whisper-large-v3-ru
```

> **Fallback**: если директории пусты, сервис Whisper автоматически скачает `large-v3` из Hugging Face при старте.

#### GigaAM ONNX (транскрибация + forced alignment)

```bash
huggingface-cli download salute-developers/GigaAM-v3-e2e-rnnt \
  --local-dir ML/onnx_gigaam_service/models/gigaam_v3_e2e_rnnt

# GigaAM v3 CTC (опционально)
huggingface-cli download salute-developers/GigaAM-v3-e2e-ctc \
  --local-dir ML/onnx_gigaam_service/models/gigaam_v3_e2e_ctc
```

> Если модели нет в открытом доступе — обратитесь к разработчикам GigaAM (Сбер) для получения ONNX-файлов.

#### Модели с авто-загрузкой (ручное скачивание не требуется)

| Сервис | Модель | Загружается |
|--------|--------|-------------|
| `denoiser` | DeepFilterNet | При первом `import` в `~/.cache/deepfilternet` |
| `rag-service` | multilingual-e5-large-instruct | При старте через `sentence-transformers` (HF cache) |

---

### 3. Запустите систему

```bash
# Полная сборка и запуск всех сервисов
docker compose up --build -d

# Проверка состояния
docker compose ps

# Логи конкретного сервиса
docker compose logs -f api
docker compose logs -f audio-ml-whisper
```

**Важно:** первый запуск собирает образы (CUDA, PyTorch, ONNX Runtime) — это может занять 15–30 минут в зависимости от скорости интернета и CPU.

---

### 4. Проверьте работоспособность

```bash
# Swagger API
curl http://localhost:8000/docs

# ML-сервисы
curl http://localhost:8052/health   # Denoiser
curl http://localhost:8053/health   # Pyannote + LLM
curl http://localhost:8054/health   # Whisper
curl http://localhost:8055/health   # RAG
curl http://localhost:8056/health   # GigaAM

# Инфраструктура
curl http://localhost:9001           # MinIO Console
curl http://localhost:6333           # Qdrant
curl http://localhost:3000/health    # Meeting Bot
```

---

### 5. Запустите фронтенд

Фронтенд (React 19 + Vite) **НЕ контейнеризирован** — запускается отдельно:

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Для production — соберите статику и раздавайте через nginx:

```bash
cd frontend
npm run build
# dist/ → nginx / caddy
```

---

### 6. (Опционально) Meeting Bot отдельно

```bash
cd meeting-bot

# Production-сборка
docker build -f Dockerfile.production -t meeting-bot .
docker run --rm -p 3000:3000 --shm-size=2gb \
  -e STORAGE_PROVIDER=s3 \
  -e S3_ENDPOINT=http://minio:9000 \
  -e S3_ACCESS_KEY_ID=... \
  -e S3_SECRET_ACCESS_KEY=... \
  -e S3_BUCKET_NAME=meeting-recordings \
  meeting-bot

# Development
docker compose up --build
```

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React 19)                        │
│       Vite + Tailwind CSS 4 + TanStack Query + Zustand          │
│       10 страниц: Dashboard • Анализ • Поиск • Профиль          │
│       Админка • Meeting Bot • Настройки • CRM и др.             │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP (REST API)
┌─────────────────────────▼───────────────────────────────────────┐
│                     Backend API (FastAPI)                        │
│   Аутентификация • Управление митингами • Экспорт • Чат (RAG)   │
│   Загрузка аудио • Voice enrollment • CRM • Аналитика           │
└──────┬──────────┬──────────┬──────────────┬─────────────────────┘
       │          │          │              │
       ▼          ▼          ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│ Celery   │ │ Celery   │ │ Celery   │ │ PostgreSQL   │
│ Worker   │ │ Worker   │ │ Beat     │ │ + Alembic    │
│ (default)│ │(meetings)│ │          │ │              │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └──────────────┘
     │            │            │
     │      ┌─────┴─────┐      │
     │      │  Redis    │◄─────┘
     │      └───────────┘
     ▼
┌──────────────────────────────────────────────────────────────────┐
│                    ML Microservices (GPU)                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  audio-ml (порт 8053) — оркестратор                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │   │
│  │  │Pyannote  │  │ Whisper  │  │ LLM Summarizer       │   │   │
│  │  │diarize   │──│transcribe│──│ (OpenRouter/GigaChat) │   │   │
│  │  └──────────┘  └────┬─────┘  └──────────────────────┘   │   │
│  │                     │                                     │   │
│  │              ┌──────▼──────────┐                         │   │
│  │              │ GigaAM ONNX     │                         │   │
│  │              │ транскрибация + │                         │   │
│  │              │ forced alignment│ ←─── слово + таймстемпы │   │
│  │              │ (порт 8056)     │                         │   │
│  └──────────────┴─────────────────┴─────────────────────────┘   │
│                                                                  │
│  ┌────────────┐  ┌────────────┐                                  │
│  │ RAG        │  │ Denoiser   │                                  │
│  │ (Qdrant)   │  │ DeepFilter │                                  │
│  │  :8055     │  │  :8052     │                                  │
│  └────────────┘  └────────────┘                                  │
└──────────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
          ┌──────────┐           ┌──────────┐
          │  MinIO   │           │  Qdrant  │
          │ (S3)     │           │ (vector) │
          │ аудио +  │           │ :6333    │
          │ аватары  │           └──────────┘
          └──────────┘

┌──────────────────────────────────────────────────────────────────┐
│                  Meeting Bot (Node.js + Playwright)               │
│   Zoom (MediaRecorder) • Google Meet (MediaRecorder)             │
│   Microsoft Teams (FFmpeg) • Xvfb + PulseAudio                   │
│   Загрузка в MinIO • Webhook в Backend API                       │
└──────────────────────────────────────────────────────────────────┘
```

### Пайплайн обработки аудио (WhisperX-style)

```
Загрузка / Запись
      │
      ▼
┌─────────────┐
│ Denoiser    │  DeepFilterNet, батчи по 60 с
│ :8052       │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Pyannote    │  Speaker Diarization → SPEAKER_00, SPEAKER_01...
│ :8053       │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Whisper large-v3     │  GigaAM ONNX │  Два режима:
│ (текст)              │  (текст +    │
│        +             │   таймстемпы)│  Whisper → GigaAM align
│ GigaAM align_words   │              │  или GigaAM full
│ (word-level таймстемпы)             │
└──────────────┬───────────────────────┘
               │
               ▼
┌─────────────┐
│ Merge       │  Слияние диаризации + aligned words
│ :8053       │  Каждое слово → к своему SPEAKER_XX
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Speaker Identification (ECAPA-TDNN)  │  SPEAKER_XX → Реальное имя
│ Поиск в Qdrant (cosine, threshold 0.5)│  через голосовой отпечаток
└──────┬───────────────────────────────┘
       │
       ▼
┌─────────────┐   ┌─────────────┐
│ LLM Summary │   │ RAG Index   │  Sentence-aware чанкинг
│ :8053       │   │ :8055       │  → dense + sparse эмбеддинги
└──────┬──────┘   └──────┬──────┘
       │                 │
       ▼                 ▼
  ┌────────┐     ┌──────────────┐
  │Postgres│     │   Qdrant     │  Гибридный поиск (RRF)
  └────────┘     └──────────────┘
```

---

## 📦 Стек технологий

| Компонент                   | Технология                                        |
|-----------------------------|---------------------------------------------------|
| Backend API                 | FastAPI + Celery + SQLAlchemy                     |
| База данных                 | PostgreSQL 17 + Alembic (миграции)                |
| Брокер очередей             | Redis 7 + Redis Commander (UI)                    |
| Файловое хранилище          | MinIO (S3-совместимое)                            |
| Векторная БД                | Qdrant 1.13 (гибридный dense + sparse)            |
| Аутентификация              | JWT (access + refresh токены, bcrypt)             |
| Frontend                    | React 19 + TypeScript + Vite + Tailwind CSS 4     |
| UI-компоненты               | Headless UI + Heroicons + Recharts                |
| Стейт-менеджмент            | Zustand + TanStack Query                          |
| Маршрутизация               | React Router v7                                   |
| **ML: Транскрибация**       | faster-whisper (large-v3, int8) / GigaAM RNNT+CTC (ONNX) |
| **ML: Диаризация**          | pyannote.audio 4.x (Hugging Face)                 |
| **ML: Шумоподавление**      | DeepFilterNet                                     |
| **ML: Forced Alignment**    | GigaAM ONNX (встроенный RNN-T декодер)            |
| **ML: Speaker ID**          | ECAPA-TDNN (SpeechBrain) + Qdrant                 |
| **ML: Суммаризация**        | LLM (OpenRouter / GigaChat / Gemini)              |
| **ML: RAG**                 | multilingual-e5-large-instruct (sentence-transformers) + Qdrant |
| **Meeting Bot**             | Node.js + TypeScript + Playwright + Express + FFmpeg |
| **Тестирование**            | pytest + pytest-mock                              |
| **Контейнеризация**         | Docker + Docker Compose, NVIDIA Container Toolkit  |

---

## 🧩 Сервисы (docker-compose)

| Сервис                | Порт  | Описание                                              |
|-----------------------|-------|-------------------------------------------------------|
| `api`                 | 8000  | FastAPI backend                                       |
| `postgres`            | 5430  | PostgreSQL 17                                         |
| `redis`               | 6379  | Redis (Celery broker)                                 |
| `redis-commander`     | 8081  | Redis UI                                              |
| `adminer`             | 8080  | PostgreSQL UI                                         |
| `minio`               | 9000  | S3-совместимое хранилище (аудио, аватары)             |
| `celery-worker-default` | —   | Celery worker — очередь `default` (транскрибация, суммаризация) |
| `celery-worker-meetings` | —  | Celery worker — очередь `meetings` (уведомления от бота) |
| `celery-beat`         | —     | Celery beat (планировщик)                              |
| `audio-ml`            | 8053  | Оркестратор: диаризация (pyannote) + суммаризация (LLM) |
| `audio-ml-whisper`    | 8054  | Транскрибация (faster-whisper large-v3)               |
| `onnx-gigaam`         | 8056  | Транскрибация (GigaAM RNNT/CTC ONNX) + **forced alignment** (word-level таймстемпы) |
| `denoiser`            | 8052  | Шумоподавление (DeepFilterNet)                        |
| `rag-service`         | 8055  | RAG-поиск по транскриптам (гибридный dense + sparse)  |
| `qdrant`              | 6333  | Векторная БД для RAG и голосовых профилей              |
| `meeting-bot`         | 3000  | Playwright бот для записи встреч                       |

> **Примечание:** Отдельный сервис `forced-aligner` (Qwen3-ForcedAligner-0.6B) — legacy, закомментирован в `docker-compose.yml`. Word-level alignment выполняется сервисом `onnx-gigaam` через эндпоинт `/align_words`.

---

## 📁 Структура репозитория

```
├── backend/
│   ├── api/                     # FastAPI + Celery + Alembic
│   │   └── app/
│   │       ├── main.py          # Точка входа API
│   │       ├── celery_app.py    # Celery конфигурация
│   │       ├── audio_utils.py   # Нормализация аудио
│   │       ├── tasks/           # Celery-задачи (пайплайн)
│   │       ├── auth_service/    # JWT аутентификация
│   │       ├── db_service/      # PostgreSQL + MinIO клиенты
│   │       ├── models/          # SQLAlchemy модели
│   │       ├── voice/           # Голосовая идентификация (ECAPA-TDNN + Qdrant)
│   │       ├── crm/             # Weeek CRM интеграция
│   │       └── tests/           # Unit-тесты (pytest)
│   └── db/                      # Данные PostgreSQL
├── frontend/                    # React 19 + TypeScript + Vite
│   └── src/
│       ├── pages/               # 10 страниц (Dashboard, Анализ, Поиск, Профиль...)
│       ├── components/          # UI-компоненты (audio, analysis, crm, voice...)
│       ├── api/                 # API-клиенты (Axios)
│       ├── hooks/               # React-хуки (useAuth, useTranscripts, useCRM...)
│       ├── context/             # AuthContext, ThemeContext, SidebarContext
│       ├── config/              # Настройки моделей, pipeline
│       └── types/               # TypeScript-типы
├── meeting-bot/                 # Playwright бот (Node.js + TypeScript)
│   ├── src/bots/                # ZoomBot, GoogleMeetBot, MicrosoftTeamsBot
│   ├── src/uploader/            # Загрузка в S3 / Azure Blob
│   └── src/connect/             # Redis consumer, webhook нотификации
├── ML/
│   ├── diarization_summarization_service/   # Оркестратор (pyannote + LLM + merge)
│   ├── whisper_transcription_service/       # faster-whisper large-v3
│   ├── onnx_gigaam_service/                 # GigaAM ASR + forced alignment
│   ├── noise_suppression_service/           # DeepFilterNet
│   ├── forced_aligner_service/              # ⚠️ Legacy (Qwen3, закомменчен)
│   └── rag-service/                         # Гибридный RAP (e5 + Qdrant)
├── docker-compose.yml
└── .env.example
```

---

## 🧪 Тестирование

Проект использует `pytest` + `pytest-mock` для unit-тестирования.

### Запуск тестов

```bash
cd backend/api
pytest app/tests/ -v
```

### Что покрыто тестами

| Модуль | Тесты | Описание |
|--------|-------|----------|
| `split_into_chunks` | 10 тестов | Разбиение транскрипции на чанки для RAG — пустой список, множество частей, конвертация ms→с, UUID→str, все ключи чанка, missing meta-поля |
| `update_task_status` | 3 теста | Обновление статуса Celery-задачи через БД (processing, completed, failed) |
| `_get_enrolled_speakers` | 4 теста | Graceful degradation при отсутствии voice-модуля (ImportError, Exception, пустой/полный список) |
| `_apply_speaker_labels_to_parts` | 3 теста | Подстановка имён спикеров в БД — matched/unmatched/speaker без colon |
| RAG sentence splitter | 2 теста | Sentence-aware чанкинг |
| RAG vector DB | 2 теста | Индексация и поиск |

### Датасеты для валидации ASR

- **Golos** — открытый датасет русской речи (Сбер / сообщество). Используется для валидации GigaAM и Whisper на русском языке: диалоги, переговоры, спонтанная речь, различные акустические условия.
- **Open STT** — открытый набор данных русской речи с текстовой расшифровкой и метаданными дикторов. Используется для бенчмаркинга Whisper vs GigaAM на русском языке, включая оценку совместной работы шумоподавления + ASR.

---

## 🎤 Идентификация спикеров по голосу

Уникальная функция Meeting Insight — возможность **сопоставить SPEAKER_XX с реальным человеком**:

1. **Enrollment**: пользователь записывает 10–30 секунд чистой речи в личном кабинете
2. **Эмбеддинг**: ECAPA-TDNN (SpeechBrain) извлекает 192-мерный голосовой вектор
3. **Хранение**: эмбеддинг сохраняется в Qdrant вместе с user_id и full_name
4. **В пайплайне**: для каждого уникального SPEAKER_XX вырезается до 60 секунд аудио (ffmpeg), извлекается эмбеддинг, ищется ближайший профиль в Qdrant (cosine similarity, threshold 0.5)
5. **Результат**: SPEAKER_00 → "Иван Иванов" в транскрипте и интерфейсе

API: `POST /voice/enroll`, `GET /voice/profile`, `DELETE /voice/profile`, `POST /voice/identify-batch`

---

## 🔍 RAG-поиск

Гибридный семантический поиск по всем транскриптам пользователя:

- **Embedding model**: `multilingual-e5-large-instruct` (1024-dim, sentence-transformers)
- **Sentence-aware чанкинг**: регулярное выражение → предложения → группировка в чанки 150-400 символов с перекрытием 1 предложение
- **Dense поиск**: cosine similarity по dense-эмбеддингам
- **Sparse поиск**: BM25-style bag-of-words, IDF-взвешенный, 30k-dim хэшированная размерность
- **Слияние**: Reciprocal Rank Fusion (RRF) для объединения dense + sparse результатов
- **Фильтры**: тип встречи, спикер, заголовок, диапазон дат, область видимости пользователя
- Две векторные БД: **Qdrant** (по умолчанию, гибридный) или **Milvus** (dense-only)

API: `POST /rag/index`, `POST /rag/search`

---

## 🔐 Аутентификация и роли

- **JWT** (access token + refresh token)
- **Две роли**: `user` (стандарт) и `admin` (управление пользователями, просмотр всех данных)
- Регистрация: фамилия, имя, отчество, email, логин, пароль
- Автоматический refresh токена на фронтенде (Axios interceptor)

---

## 📊 Фронтенд — страницы

| Страница | Маршрут | Функции |
|----------|---------|---------|
| Login / Register | `/login`, `/register` | JWT-аутентификация |
| Dashboard | `/` | 9 последних встреч, drag-and-drop загрузка, прогресс задач |
| Новый анализ | `/new-analysis` | Настройка моделей, загрузка аудио |
| Анализ встречи | `/analysis/:id` | Транскрипт со спикерами, аудиоплеер, summary, RAG-чат, аннотации, CRM-задачи, графики |
| Meeting Bot | `/meeting-bot` | Подключение к Zoom/Meet/Teams, календарь |
| Поиск | `/search` | RAG-поиск с фильтрами |
| Профиль | `/profile` | Редактирование профиля, аватар, голосовая регистрация |
| Настройки | `/settings` | Модели по умолчанию, CRM API токен, тема |
| Админка | `/admin` | Пользователи, транскрипты, аналитика (DAU/MAU, ASR performance) |
| Все встречи | `/all-meetings` | Таблица транскриптов с фильтрами и пагинацией |

---

## 🔄 CRM-интеграция (Weeek)

- **Просмотр**: проекты, доски, колонки, участники Weeek
- **Извлечение задач**: из summary встречи → структурированные задачи (ответственный, дедлайн)
- **Отправка**: создание задач в Weeek через CRM API
- **Локальное хранение**: assignee и deadline на фронтенде до отправки

---

## 🔐 Переменные окружения (.env)

### Аутентификация и LLM

| Переменная | Значение по умолч. | Назначение |
|-----------|-------------------|-----------|
| `JWT_SECRET_KEY` | — | **Обязательная.** Секретный ключ для JWT (`openssl rand -hex 32`) |
| `JWT_ALGORITHM` | `HS256` | Алгоритм подписи JWT |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Время жизни access token (минуты) |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Время жизни refresh token (дни) |
| `HF_API_KEY` | — | **Обязательная.** Hugging Face токен (доступ к `pyannote/speaker-diarization-community`) |
| `OPENAI_API_KEY` | — | **Обязательная.** Ключ LLM для суммаризации (OpenRouter / GigaChat / Gemini) |
| `OPENAI_BASE_URL` | `https://openrouter.ai/api/v1` | Базовый URL LLM провайдера |

### Пути к ML-моделям (внутри контейнера)

| Переменная | Значение по умолч. | Назначение |
|-----------|-------------------|-----------|
| `PYANNOTE_MODEL_PATH` | `/app/models/pyannote` | Путь к модели диаризации Pyannote |
| `GIGAAM_MODEL_PATH` | `/app/models/gigaam_v3_e2e_rnnt` | Путь к GigaAM ONNX модели |
| `WHISPER_MODEL_PATH` | `/app/models/faster-distil-whisper-large-v3-ru` | Путь к Whisper модели |
| `FORCED_ALIGNER_MODEL_PATH` | `/app/models/qwen3-0.6b` | ⚠️ Legacy (Qwen3, сервис закомменчен) |
| `SILERO_VAD_MODEL_PATH` | `/app/models/silero-vad/model.onnx` | ⚠️ Legacy (Silero VAD для Qwen3) |

### База данных

| Переменная | Значение по умолч. | Назначение |
|-----------|-------------------|-----------|
| `POSTGRES_USER` | — | **Обязательная.** Пользователь PostgreSQL |
| `POSTGRES_PASSWORD` | — | **Обязательная.** Пароль PostgreSQL |
| `POSTGRES_DB` | — | **Обязательная.** Имя БД PostgreSQL |
| `DB_HOST` | — | Хост PostgreSQL |
| `DB_PORT` | — | Порт PostgreSQL |

### Векторная БД

| Переменная | Значение по умолч. | Назначение |
|-----------|-------------------|-----------|
| `VECTOR_DB` | `qdrant` | Выбор БД: `qdrant` (гибридный dense+sparse) или `milvus` (dense-only) |
| `QDRANT_HOST` | — | Хост Qdrant |
| `QDRANT_INTERNAL_PORT` | — | Внутренний порт Qdrant |
| `QDRANT_HOST_PORT` | — | Внешний порт Qdrant |
| `MILVUS_HOST` | — | Хост Milvus |
| `MILVUS_INTERNAL_PORT` | — | Внутренний порт Milvus |
| `MILVUS_HOST_PORT` | — | Внешний порт Milvus |
| `MILVUS_PORT` | — | Порт Milvus |

### Хранилище (MinIO)

| Переменная | Значение по умолч. | Назначение |
|-----------|-------------------|-----------|
| `MINIO_ROOT_USER` | — | **Обязательная.** Пользователь MinIO admin |
| `MINIO_ROOT_PASSWORD` | — | **Обязательная.** Пароль MinIO admin |
| `S3_BUCKET_NAME` | — | Имя S3-бакета для записей |
| `AVATAR_BUCKET_NAME` | — | Имя бакета для аватарок |
| `AUDIO_BUCKET_NAME` | — | Имя бакета для аудиофайлов |
| `MINIO_PUBLIC_ENDPOINT` | — | Публичный endpoint MinIO для браузера |

### Meeting Bot

| Переменная | Значение по умолч. | Назначение |
|-----------|-------------------|-----------|
| `MEETING_BOT_URL` | — | URL Meeting Bot сервиса |
| `MEETING_BOT_WEBHOOK_SECRET` | — | Секрет вебхука от Meeting Bot |
| `MAX_RECORDING_DURATION_MINUTES` | `180` | Макс. длительность записи (мин) |
| `MEETING_INACTIVITY_MINUTES` | `2` | Таймаут бездействия для остановки записи |
| `INACTIVITY_DETECTION_START_DELAY_MINUTES` | `5` | Задержка перед началом детекции бездействия |
| `JOIN_WAIT_TIME_MINUTES` | `2` | Ожидание в lobby перед таймаутом |
| `RETRY_COUNT` | `2` | Число повторных попыток при ошибках |

### Прочее

| Переменная | Значение по умолч. | Назначение |
|-----------|-------------------|-----------|
| `WEEEK_PUBLIC_API` | — | API ключ для интеграции с Weeek CRM |
| `PGADMIN_DEFAULT_EMAIL` | — | Email для pgAdmin (UI для PostgreSQL) |
| `PGADMIN_DEFAULT_PASSWORD` | — | Пароль для pgAdmin |
| `AUDIO_ML_TIMEOUT` | — | Таймаут пайплайна (сек), по умолч. 1200 |

---

## 🤝 Вклад в проект

Мы приветствуем Pull Request'ы. Пожалуйста, убедитесь, что:

1. `docker compose build` проходит успешно.
2. ML-сервисы корректно отвечают на `/health` эндпоинты.
3. Тесты проходят: `pytest backend/api/app/tests/ -v`.
4. Добавлены тесты для новой функциональности (если применимо).

---

## 📄 Лицензия

MIT
