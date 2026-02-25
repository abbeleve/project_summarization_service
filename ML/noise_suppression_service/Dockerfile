# Базовый образ с CUDA 12.8 (используем ваш кэшированный образ)
FROM nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04

# Устанавливаем Python и зависимости
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
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Rust (требуется для deepfilternet)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Устанавливаем PyTorch с CUDA 12.8
RUN pip install --no-cache-dir --break-system-packages --ignore-installed \
    torch==2.4.0 \
    torchaudio==2.4.0 \
    --index-url https://download.pytorch.org/whl/cu124

# Устанавливаем зависимости
RUN pip install --no-cache-dir --break-system-packages \
    fastapi \
    uvicorn \
    python-multipart \
    soundfile \
    requests

# Устанавливаем deepfilternet (стабильная версия с PyPI)
RUN pip install --no-cache-dir --break-system-packages \
    deepfilternet==0.5.6

# Переменные окружения для CUDA
ENV CUDA_LAUNCH_BLOCKING=1
ENV TORCH_CUDA_ARCH_LIST="8.0;8.6;8.9;9.0"

COPY denoise.py /app/denoise.py
COPY main.py /app/main.py

WORKDIR /app

EXPOSE 8052

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8052"]