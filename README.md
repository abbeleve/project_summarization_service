# 🎙️ Meeting Insight — Автоматическая обработка встреч

> **Диаризация • Транскрибация • Суммаризация**  
> Сервис для полного анализа аудиозаписей встреч: кто говорил, что сказал и главное — в чём суть?

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-black?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue?logo=docker)](https://www.docker.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-orange?logo=streamlit)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📌 Описание

**Meeting Insight** — это полный пайплайн для автоматической обработки аудиозаписей совещаний:

1. **Диаризация речи** — определение, кто из участников говорил и когда (`pyannote.audio`).
2. **Транскрибация** — преобразование речи в текст с разбивкой по спикерам (`faster-whisper`).
3. **Суммаризация** — генерация краткого содержания с помощью современных LLM (например, через OpenRouter или GigaChat).

Сервис разработан с учётом сложной зависимости версий между ML-библиотеками — каждая стадия изолирована в отдельный Docker-контейнер, а взаимодействие между ними происходит через унифицированный FastAPI-бэкенд. Интерфейс для пользователей и аналитиков реализован на **Streamlit**.

---

## 🚀 Основные возможности

- Поддержка аудиоформатов: `WAV`, `MP3`, `OGG`, `MP4` (аудиодорожка).
- Автоматическое определение числа спикеров.
- Сохранение временных меток и привязка текста к говорящему.
- Экспорт транскрипции в текстовый файл или JSON.
- Краткое содержание встречи по запросу (настраиваемые промпты).
- Готов к развёртыванию в Docker-окружении с GPU-ускорением.

---

## 📦 Стек технологий

| Компонент           | Технология / Библиотека             |
|---------------------|-------------------------------------|
| Backend API         | FastAPI                             |
| Диаризация          | `pyannote.audio` (Hugging Face)     |
| Транскрибация       | `faster-whisper` (Whisper large-v3) |
| Суммаризация        | LLM через OpenRouter / GigaChat API |
| Frontend / UI       | Streamlit                           |
| Контейнеризация     | Docker + Docker Compose             |
| Аудиообработка      | `torchaudio`, `ffmpeg`              |
| Язык                | Python 3.10+                        |

---

## 🛠️ Быстрый старт

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/your-username/meeting-insight.git
cd meeting-insight
