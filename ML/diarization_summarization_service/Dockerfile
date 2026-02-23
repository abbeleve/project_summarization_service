FROM nvcr.io/nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv git git-lfs \
        ffmpeg libsndfile1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Клонируем и устанавливаем GigaAM
RUN git clone https://github.com/salute-developers/GigaAM.git /app/GigaAM && \
    pip install -e /app/GigaAM

RUN mkdir -p /app/models/pyannote

WORKDIR /app

COPY ./prompts ./prompts
COPY ML_pipeline.py .
COPY main.py .
COPY noise_suppression_request.py .
COPY whisper_request.py .
COPY ontology.txt .

EXPOSE 8053

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8053"]