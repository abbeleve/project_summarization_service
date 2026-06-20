# 🎙️ Meeting Insight — Автоматическая обработка встреч

> **Диаризация • Транскрибация • Суммаризация • RAG**
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
2. **Шумоподавление** — очистка аудиодорожки перед распознаванием.
3. **Транскрибация** — распознавание речи в текст (Whisper large-v3 или GigaAM RNNT/CTC).
4. **Диаризация** — определение, кто и когда говорил (`pyannote.audio`).
5. **Forced Alignment** — покадровая привязка слов к временным меткам (Qwen3-0.6B).
6. **Суммаризация** — генерация краткого содержания через LLM (OpenRouter / GigaChat).
7. **RAG** — семантический поиск по транскриптам (Qdrant + эмбеддинги).

Каждая стадия изолирована в собственный Docker-контейнер с GPU-ускорением. Фронтенд — React 19 + TypeScript.

---

## 🚀 Основные возможности

- Автоматическое подключение к Zoom / Google Meet / Teams через Playwright-бота
- Поддержка загружаемых аудио: `WAV`, `MP3`, `OGG`, `MP4` (аудиодорожка)
- Автоматическое определение числа спикеров
- Временные метки с привязкой текста к говорящему (word-level alignment)
- Шумоподавление перед распознаванием
- Два ASR-движка на выбор: Whisper large-v3 (мультиязычный) и GigaAM (русский)
- Краткое содержание встречи по запросу (настраиваемые промпты)
- RAG-поиск по истории транскриптов
- Экспорт транскрипции в TXT / JSON
- JWT-аутентификация, управление пользователями (личный кабинет)
- Готов к развёртыванию в Docker-окружении с NVIDIA GPU

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React 19)                     │
│                   Vite + Tailwind CSS + Recharts                │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP (REST API)
┌─────────────────────────▼───────────────────────────────────────┐
│                     Backend API (FastAPI)                        │
│            Аутентификация • Управление митингами • Экспорт       │
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
│                     ML Microservices (GPU)                       │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐ │
│  │ Whisper    │  │ GigaAM     │  │ Denoiser   │  │ Pyannote  │ │
│  │ (transc.)  │  │ (transc.)  │  │ (denoise)  │  │(diarize)  │ │
│  │  :8054     │  │  :8056     │  │  :8052     │  │  :8053    │ │
│  └────────────┘  └────────────┘  └────────────┘  └─────┬─────┘ │
│                                                         │       │
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐    │       │
│  │ RAG        │  │ Forced     │  │ Summarization  │◄───┘       │
│  │ (Qdrant)   │  │ Aligner    │  │ (LLM)          │            │
│  │  :8055     │  │  :8057     │  │  :8053         │            │
│  └────────────┘  └────────────┘  └────────────────┘            │
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
│              Zoom • Google Meet • Microsoft Teams                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📦 Стек технологий

| Компонент                 | Технология                                      |
|---------------------------|--------------------------------------------------|
| Backend API               | FastAPI + Celery + SQLAlchemy                    |
| База данных               | PostgreSQL 17                                    |
| Брокер очередей           | Redis 7 + Redis Commander (UI)                   |
| Файловое хранилище        | MinIO (S3-совместимое)                           |
| Векторная БД              | Qdrant 1.13                                     |
| Аутентификация            | JWT (access + refresh токены)                   |
| Frontend                  | React 19 + TypeScript + Vite + Tailwind CSS 4   |
| UI-компоненты             | Headless UI + Heroicons + Recharts              |
| Стейт-менеджмент          | Zustand + TanStack Query                        |
| Маршрутизация             | React Router v7                                 |
| **ML: Транскрибация**     | faster-whisper (large-v3) / GigaAM RNNT+CTC     |
| **ML: Диаризация**        | pyannote.audio (Hugging Face)                   |
| **ML: Шумоподавление**    |专用 noise suppression service                   |
| **ML: Forced Alignment**  | Qwen3-ForcedAligner-0.6B                        |
| **ML: Суммаризация**      | LLM (OpenRouter / GigaChat API)                 |
| **ML: RAG**               | Собственный RAG-сервис на Qdrant                 |
| **Meeting Bot**           | Node.js + TypeScript + Playwright + Express     |
| Контейнеризация           | Docker + Docker Compose, NVIDIA Container Tookit |
| Миграции БД               | Alembic                                         |

---

## 🛠️ Быстрый старт

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/your-username/meeting-insight.git
cd meeting-insight
```

### 2. Настройте окружение

```bash
cp .env.example .env
# Отредактируйте .env: API-ключи (HF_API_KEY, OPENAI_API_KEY, JWT_SECRET_KEY и т.д.)
```

### 3. Запустите все сервисы

```bash
docker compose up --build
```

После запуска:
- **API**: http://localhost:8000
- **Frontend**: http://localhost:8502
- **MinIO Console**: http://localhost:9001
- **Redis Commander**: http://localhost:8081
- **Adminer** (БД): http://localhost:8080
- **Qdrant**: http://localhost:6333

### 4. Самостоятельная загрузка аудио

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@meeting.wav" \
  -H "Authorization: Bearer <token>"
```

### 5. Автоматическая запись встречи

```bash
curl -X POST http://localhost:3000/meeting \
  -H "Content-Type: application/json" \
  -d '{"url": "https://zoom.us/j/123456789", "platform": "zoom"}'
```

---

## 🧩 Сервисы (docker-compose)

| Сервис                | Порт  | Описание                                    |
|-----------------------|-------|---------------------------------------------|
| `api`                 | 8000  | FastAPI backend                             |
| `postgres`            | 5430  | PostgreSQL 17                               |
| `redis`               | 6379  | Redis (Celery broker)                       |
| `redis-commander`     | 8081  | Redis UI                                    |
| `adminer`             | 8080  | PostgreSQL UI                               |
| `minio`               | 9000  | S3-совместимое хранилище                    |
| `celery-worker-default` | —   | Celery worker (транскрибация, суммаризация) |
| `celery-worker-meetings` | —  | Celery worker (уведомления от бота)         |
| `celery-beat`         | —     | Celery beat (расписание задач)              |
| `audio-ml`            | 8053  | Диаризация + суммаризация (pyannote + LLM)  |
| `audio-ml-whisper`    | 8054  | Транскрибация (Whisper large-v3)            |
| `onnx-gigaam`         | 8056  | Транскрибация (GigaAM RNNT/CTC)             |
| `denoiser`            | 8052  | Шумоподавление                              |
| `forced-aligner`      | 8057  | Word-level forced alignment (Qwen3-0.6B)    |
| `rag-service`         | 8055  | RAG-поиск по транскриптам (Qdrant)          |
| `qdrant`              | 6333  | Векторная БД                                |
| `meeting-bot`         | 3000  | Playwright бот для записи встреч            |

---

## 📁 Структура репозитория

```
├── backend/
│   ├── api/                     # FastAPI + Celery + Alembic
│   └── db/                      # Данные PostgreSQL
├── frontend/                    # React 19 + TypeScript + Vite
├── meeting-bot/                 # Playwright бот (Node.js + TypeScript)
├── ML/
│   ├── diarization_summarization_service/   # Pyannote + LLM
│   ├── whisper_transcription_service/       # faster-whisper
│   ├── onnx_gigaam_service/                 # GigaAM ASR
│   ├── noise_suppression_service/           # Шумоподавление
│   ├── forced_aligner_service/              # Qwen3 ForcedAligner
│   └── rag-service/                         # RAG поверх Qdrant
├── docker-compose.yml
└── .env.example
```

---

## 🔐 Переменные окружения (.env)

| Переменная                     | Назначение                              |
|--------------------------------|-----------------------------------------|
| `POSTGRES_USER/PASSWORD/DB`    | Учётные данные PostgreSQL               |
| `JWT_SECRET_KEY/ALGORITHM`     | JWT-аутентификация                      |
| `HF_API_KEY`                   | Hugging Face токен (pyannote)           |
| `OPENAI_API_KEY`               | OpenAI/OpenRouter ключ (суммаризация)   |
| `MINIO_ROOT_USER/PASSWORD`     | MinIO root credentials                  |
| `MEETING_BOT_WEBHOOK_SECRET`   | Секрет вебхука от Meeting Bot           |

Полный список — в файле `.env.example`.

---

## 🤝 Вклад в проект

Мы приветствуем Pull Request'ы. Пожалуйста, убедитесь, что:

1. `docker compose build` проходит успешно.
2. ML-сервисы корректно отвечают на `/health` эндпоинты.
3. Добавлены тесты для новой функциональности (если применимо).

---

## 📄 Лицензия

MIT
