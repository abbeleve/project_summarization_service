# ML/rag-service/download_embedder.py
from sentence_transformers import SentenceTransformer
import os

MODEL_NAME = "intfloat/multilingual-e5-large-instruct"
SAVE_PATH = "./models/multilingual-e5-large-instruct"

if __name__ == "__main__":
    print(f"📥 Скачивание модели {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    print(f"💾 Сохранение в {os.path.abspath(SAVE_PATH)}...")
    model.save(SAVE_PATH)
    print("✅ Готово!")