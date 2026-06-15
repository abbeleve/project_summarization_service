# Используем официальный образ Python 3.9
FROM python:3.9-slim

# Установим зависимости ОС
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

# Установим pip
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.9

# Установим зависимости Python
RUN python3.9 -m pip install torch torchaudio soundfile deepfilternet fastapi uvicorn python-multipart librosa

# Копируем скрипты
COPY denoise.py /app/denoise.py
COPY main.py /app/main.py

WORKDIR /app

EXPOSE 8052

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8052"]