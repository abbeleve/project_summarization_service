FROM nvcr.io/nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv git git-lfs curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

WORKDIR /app

RUN mkdir -p /app/models/whisper
RUN mkdir -p /app/models/faster-distil-whisper-large-v3-ru

EXPOSE 8054

COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8054"]