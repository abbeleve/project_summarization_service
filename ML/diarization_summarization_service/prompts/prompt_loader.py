import yaml
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class PromptLoader:
    """Загрузчик промптов из YAML-файла с поддержкой кэширования и fallback."""
    
    def __init__(self, yaml_path: str = "prompts/llm_prompts.yaml"):
        self.yaml_path = Path(yaml_path)
        self._prompts: Optional[Dict[str, Any]] = None
        self._load()
    
    def _load(self) -> None:
        """Загружает YAML-файл с промптами."""
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {self.yaml_path}")
        
        try:
            with open(self.yaml_path, "r", encoding="utf-8") as f:
                self._prompts = yaml.safe_load(f)
            logger.info(f"Prompts loaded from {self.yaml_path}")
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML: {e}")
            raise
    
    def get(self, path: str, default: Optional[str] = None) -> Optional[str]:
        """
        Получает промпт по точечному пути, например 'summarization.system'.
        
        Args:
            path: Точечный путь к значению в YAML
            default: Значение по умолчанию, если ключ не найден
            
        Returns:
            Строка промпта или None/default
        """
        if self._prompts is None:
            self._load()
        
        keys = path.split(".")
        value = self._prompts
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            if default is not None:
                return default
            logger.warning(f"Prompt path '{path}' not found in {self.yaml_path}")
            return None
    
    def format(self, path: str, **kwargs) -> Optional[str]:
        """
        Получает промпт и форматирует его через .format(**kwargs).
        Удобно для промптов с плейсхолдерами, например {ontology}.
        """
        prompt = self.get(path)
        if prompt is None:
            return None
        try:
            return prompt.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing key for prompt formatting: {e}")
            return prompt  # возвращаем как есть, если форматирование не удалось