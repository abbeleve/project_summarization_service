# Используем NVIDIA образ с предустановленным CUDA 11.8 и cuDNN
FROM nvcr.io/nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-dev \
        git \
        curl \
        libsndfile1 \
        ffmpeg \
        pkg-config \
        libssl-dev \
        libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Сначала обновляем pip
RUN pip install --no-cache-dir --upgrade pip

# Установка Python зависимостей
# torch с CUDA 11.8 совместим с образом NVIDIA
RUN pip install --no-cache-dir \
    torch==2.0.1 \
    torchaudio==2.0.2 \
    soundfile==0.12.1 \
    deepfilternet==0.5.0 \
    fastapi==0.109.2 \
    uvicorn==0.27.0 \
    python-multipart==0.0.7

# Копирование файлов приложения
COPY denoise.py /app/denoise.py
COPY main.py /app/main.py

WORKDIR /app

EXPOSE 8052

# Запуск с логированием
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8052", "--log-level", "info"]
