import os
import io
import logging
from uuid import UUID
from typing import Optional
from datetime import timedelta
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinioClient:
    """Клиент для работы с MinIO (S3-совместимое хранилище).

    Используется для хранения и раздачи аватарок пользователей.
    """

    def __init__(self):
        endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        access_key = os.getenv("MINIO_ROOT_USER", "minioadmin")
        secret_key = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
        self.bucket = os.getenv("AVATAR_BUCKET_NAME", "avatars")
        self.AUDIO_BUCKET = os.getenv("AUDIO_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME", "meeting-recordings")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

        # Публичный endpoint для presigned URL (со стороны браузера)
        self._public_endpoint = os.getenv("MINIO_PUBLIC_ENDPOINT", "localhost:9000")

        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Создаёт bucket если его ещё нет."""
        for bucket_name in (self.bucket, self.AUDIO_BUCKET):
            try:
                if not self.client.bucket_exists(bucket_name):
                    self.client.make_bucket(bucket_name)
                    logger.info("Created bucket: %s", bucket_name)
            except S3Error as e:
                logger.error("Failed to ensure bucket %s: %s", bucket_name, e)

    @staticmethod
    def _avatar_key(user_id: UUID) -> str:
        return str(user_id)

    def upload_avatar(self, user_id: UUID, data: bytes, content_type: str) -> str:
        """Загружает аватарку в MinIO.

        Returns:
            Ключ загруженного объекта.
        """
        key = self._avatar_key(user_id)
        self.client.put_object(
            self.bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        logger.info("Avatar uploaded: %s", key)
        return key

    def delete_avatar(self, user_id: UUID) -> bool:
        """Удаляет аватарку из MinIO.

        Returns:
            True если объект был удалён или не существовал.
        """
        key = self._avatar_key(user_id)
        try:
            self.client.remove_object(self.bucket, key)
            logger.info("Avatar deleted: %s", key)
            return True
        except S3Error as e:
            logger.warning("Failed to delete avatar %s: %s", key, e)
            return False

    def get_avatar_data(self, user_id: UUID) -> Optional[tuple[bytes, str]]:
        """Получает данные аватарки и content-type из MinIO.

        Returns:
            Кортеж (bytes, content_type) или None если объект не найден.
        """
        key = self._avatar_key(user_id)
        try:
            response = self.client.get_object(self.bucket, key)
            data = response.read()
            content_type = response.getheader("Content-Type", "image/png")
            response.close()
            response.release_conn()
            return data, content_type
        except S3Error:
            return None

    def avatar_exists(self, user_id: UUID) -> bool:
        """Проверяет существует ли аватарка в MinIO."""
        key = self._avatar_key(user_id)
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except S3Error:
            return False

    def get_avatar_url(self, user_id: UUID, expires_seconds: int = 3600) -> Optional[str]:
        """Генерирует presigned URL для аватарки (без авторизации).

        URL указывает на публичный endpoint MinIO и действителен
        ограниченное время.

        Returns:
            Presigned URL или None если объект не найден.
        """
        key = self._avatar_key(user_id)
        try:
            # Сначала проверяем что объект существует
            self.client.stat_object(self.bucket, key)
            # Генерируем presigned URL
            url = self.client.presigned_get_object(
                self.bucket,
                key,
                expires=timedelta(seconds=expires_seconds),
            )
            # Подменяем внутренний endpoint (minio:9000) на публичный (localhost:9000)
            url = url.replace(f"minio:9000", self._public_endpoint)
            url = url.replace(f"https://{self._public_endpoint}", f"http://{self._public_endpoint}")
            return url
        except S3Error:
            return None

    # ========================================================================
    # AUDIO / RECORDING METHODS
    # ========================================================================

    def upload_audio(self, key: str, data: bytes, content_type: str = "audio/webm") -> str:
        """Загружает аудиофайл в MinIO (bucket: meeting-recordings).

        Args:
            key: Ключ объекта (например, uploads/{user_id}/{task_id}/audio.webm)
            data: Бинарные данные аудиофайла
            content_type: MIME-тип аудиофайла

        Returns:
            Ключ загруженного объекта.
        """
        self.client.put_object(
            self.AUDIO_BUCKET,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        logger.info("Audio uploaded: %s/%s", self.AUDIO_BUCKET, key)
        return key

    def get_audio_public_url(self, key: str) -> str:
        """Формирует публичный URL для доступа к аудиофайлу из браузера.

        Бакет meeting-recordings настроен на анонимное скачивание (см. minio-init).
        Возвращает прямой URL на публичный endpoint MinIO.

        Args:
            key: Ключ объекта в MinIO

        Returns:
            Публичный URL для воспроизведения аудио.
        """
        return f"http://{self._public_endpoint}/{self.AUDIO_BUCKET}/{key}"

    def delete_audio(self, key: str) -> bool:
        """Удаляет аудиофайл из MinIO.

        Args:
            key: Ключ объекта в MinIO

        Returns:
            True если объект был удалён или не существовал.
        """
        try:
            self.client.remove_object(self.AUDIO_BUCKET, key)
            logger.info("Audio deleted: %s/%s", self.AUDIO_BUCKET, key)
            return True
        except S3Error as e:
            logger.warning("Failed to delete audio %s/%s: %s", self.AUDIO_BUCKET, key, e)
            return False
