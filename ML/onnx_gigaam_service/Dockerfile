FROM nvcr.io/nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv git git-lfs curl \
        libsndfile1 ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Клонируем и устанавливаем GigaAM (нужен gigaam.onnx_utils)
# ВАЖНО: --no-deps, потому что GigaAM тянет onnxruntime==1.23.* (CPU),
# который перезаписывает onnxruntime-gpu, установленный из requirements.txt.
# После установки GigaAM принудительно переставляем GPU-версию.
RUN git clone https://github.com/salute-developers/GigaAM.git /app/GigaAM && \
    pip install --no-deps -e /app/GigaAM && \
    pip install --no-cache-dir onnxruntime-gpu==1.19.2

# Модели монтируются через volume (не копируются в образ)
RUN mkdir -p /app/models/gigaam_v3_e2e_rnnt /app/models/gigaam_v3_e2e_ctc

WORKDIR /app
COPY main.py .

EXPOSE 8056

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8056"]
