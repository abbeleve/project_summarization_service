from sentence_transformers import SentenceTransformer
import os

class Embedder:
    def __init__(self, model_path: str = "/app/models/multilingual-e5-large-instruct"):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Модель не найдена по пути: {model_path}")
        self.model = SentenceTransformer(model_path)
        print(f"✅ Модель загружена из: {model_path}")

    def encode(self, texts, **kwargs):
        return self.model.encode(texts, **kwargs)