"""
Клиент для сервиса шумоподавления.
Отправляет аудио на внешний denoiser сервис и получает очищенный файл.
"""
import logging
import requests
import tempfile
import os
from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)


class NoiseSuppressionClient:
    """
    Клиент для сервиса шумоподавления.
    
    Отправляет аудиофайлы на внешний сервис для подавления шума
    и получает обратно очищенный файл.
    """
    
    def __init__(
        self,
        service_url: str = None,
        timeout: int = None
    ):
        """
        Инициализация клиента.
        
        Args:
            service_url: URL сервиса шумоподавления
            timeout: Таймаут запроса (сек)
        """
        self.service_url = service_url or settings.noise_suppression_url
        self.timeout = timeout or settings.noise_suppression_timeout_sec
    
    def apply_noise_suppression(self, audio_path: str) -> str:
        """
        Применяет шумоподавление к аудиофайлу.
        
        Args:
            audio_path: Путь к входному аудиофайлу
            
        Returns:
            Путь к временному файлу с очищенным аудио
            
        Raises:
            FileNotFoundError: Если файл не найден
            RuntimeError: Если шумоподавление не удалось
        """
        try:
            if not os.path.isfile(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            logger.info(f"Отправка на шумоподавление: {audio_path}")
            
            # Отправка файла — передаём file object напрямую (requests стримит чанками)
            with open(audio_path, "rb") as f:
                files = {"file": (Path(audio_path).name, f, "audio/wav")}
                response = requests.post(
                    self.service_url,
                    files=files,
                    timeout=self.timeout
                )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Noise suppression service error: "
                    f"{response.status_code} - {response.text}"
                )

            # Сохранение результата во временный файл (чанками, без resp.content)
            temp_fd, temp_path = tempfile.mkstemp(suffix="_clean.wav")
            os.close(temp_fd)

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8_388_608):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"Шумоподавление завершено: {temp_path}")
            return temp_path
            
        except FileNotFoundError:
            logger.error(f"Файл не найден: {audio_path}")
            raise
        except requests.Timeout:
            logger.error(f"Таймаут запроса шумоподавления ({self.timeout} сек)")
            raise RuntimeError(
                f"Noise suppression timeout after {self.timeout} seconds"
            )
        except Exception as e:
            logger.error(f"Ошибка шумоподавления: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Noise suppression failed: {str(e)}") from e
    
    def apply_noise_suppression_bytes(self, audio_path: str) -> bytes:
        """
        Применяет шумоподавление и возвращает результат как байты.
        
        Args:
            audio_path: Путь к входному аудиофайлу
            
        Returns:
            Байты очищенного аудио
            
        Raises:
            FileNotFoundError: Если файл не найден
            RuntimeError: Если шумоподавление не удалось
        """
        try:
            if not os.path.isfile(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            logger.info(f"Отправка на шумоподавление (bytes): {audio_path}")

            # Отправка файла — передаём file object напрямую (requests стримит чанками)
            with open(audio_path, "rb") as f:
                files = {"file": (Path(audio_path).name, f, "audio/wav")}
                response = requests.post(
                    self.service_url,
                    files=files,
                    timeout=self.timeout
                )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Noise suppression service error: "
                    f"{response.status_code} - {response.text}"
                )

            logger.info(f"Шумоподавление завершено: {len(response.content)} байт")
            return response.content
            
        except FileNotFoundError:
            logger.error(f"Файл не найден: {audio_path}")
            raise
        except requests.Timeout:
            logger.error(f"Таймаут запроса шумоподавления ({self.timeout} сек)")
            raise RuntimeError(
                f"Noise suppression timeout after {self.timeout} seconds"
            )
        except Exception as e:
            logger.error(f"Ошибка шумоподавления: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Noise suppression failed: {str(e)}") from e
