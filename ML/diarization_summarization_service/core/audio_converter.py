"""
Модуль для конвертации аудиофайлов в WAV формат.
Использует torchaudio для загрузки и ресемплинга.
"""
import logging
import torchaudio
from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)


class AudioConverter:
    """
    Конвертер аудиофайлов в WAV формат.
    
    Конвертирует любые поддерживаемые форматы в WAV с заданной частотой дискретизации.
    """
    
    SUPPORTED_EXTENSIONS = {'.mp3', '.wav', '.mp4', '.ogg', '.flac', '.m4a'}
    
    def __init__(self, sample_rate: int = None):
        """
        Инициализация конвертера.
        
        Args:
            sample_rate: Частота дискретизации (по умолчанию из settings)
        """
        self.sample_rate = sample_rate or settings.sample_rate
    
    def is_supported(self, file_path: str) -> bool:
        """
        Проверка поддерживаемости формата файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            True если формат поддерживается
        """
        ext = Path(file_path).suffix.lower()
        return ext in self.SUPPORTED_EXTENSIONS
    
    def convert_to_wav(self, input_path: str, output_path: str) -> str:
        """
        Конвертирует аудиофайл в WAV формат.
        
        Args:
            input_path: Путь к входному файлу
            output_path: Путь для выходного WAV файла
            
        Returns:
            Путь к сконвертированному файлу
            
        Raises:
            FileNotFoundError: Если входной файл не найден
            RuntimeError: Если конвертация не удалась
        """
        try:
            logger.info(f"Конвертация '{input_path}' -> '{output_path}'")
            
            # Загрузка аудио
            waveform, sample_rate = torchaudio.load(input_path)
            logger.debug(f"Загружено: shape={waveform.shape}, sr={sample_rate}")
            
            # Конвертация в моно если стерео
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
                logger.debug("Конвертировано в моно")
            
            # Ресемплинг если нужно
            if sample_rate != self.sample_rate:
                waveform = torchaudio.functional.resample(
                    waveform, 
                    sample_rate, 
                    self.sample_rate
                )
                logger.debug(f"Ресемплинг: {sample_rate} -> {self.sample_rate} Hz")
            
            # Сохранение в WAV
            torchaudio.save(
                output_path,
                waveform,
                self.sample_rate,
                format='wav',
                encoding="PCM_S",
                bits_per_sample=16
            )
            
            logger.info(f"Успешно сконвертировано: {output_path}")
            return output_path
            
        except FileNotFoundError:
            logger.error(f"Файл не найден: {input_path}")
            raise FileNotFoundError(f"Audio file not found: {input_path}")
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            raise RuntimeError(f"Failed to convert audio: {e}") from e
    
    def get_extension(self, filename: str) -> str:
        """
        Получение расширения файла в нижнем регистре.
        
        Args:
            filename: Имя файла
            
        Returns:
            Расширение файла (например, '.wav')
        """
        return Path(filename).suffix.lower()
    
    def validate_extension(self, filename: str) -> bool:
        """
        Валидация расширения файла.
        
        Args:
            filename: Имя файла
            
        Returns:
            True если расширение поддерживается
            
        Raises:
            ValueError: Если расширение не поддерживается
        """
        ext = self.get_extension(filename)
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format: {ext}. "
                f"Supported: {', '.join(self.SUPPORTED_EXTENSIONS)}"
            )
        return True
