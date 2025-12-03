FROM nvcr.io/nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04

ARG HF_API_KEY

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv git git-lfs \
        ffmpeg libsndfile1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Клонируем модель на этапе сборки (токен используется, но не сохраняется в финальном слое)
RUN git lfs install && \
    git clone https://hf_token:${HF_API_KEY}@huggingface.co/pyannote/speaker-diarization-community-1 /app/pyannote-model

# Клонируем и устанавливаем GigaAM
RUN git clone https://github.com/salute-developers/GigaAM.git /app/GigaAM && \
    pip install -e /app/GigaAM

WORKDIR /app
COPY ML_pipeline.py .
COPY main.py .
COPY noise_suppression_request.py .

EXPOSE 8053

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8053"]