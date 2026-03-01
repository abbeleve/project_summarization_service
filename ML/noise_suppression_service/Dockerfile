FROM python:3.9-slim

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

RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.9

RUN python3.9 -m pip install torch torchaudio soundfile deepfilternet fastapi uvicorn python-multipart

RUN python -c "from df.enhance import init_df; init_df()"

COPY denoise.py /app/denoise.py
COPY main.py /app/main.py

WORKDIR /app

EXPOSE 8052

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8052"]