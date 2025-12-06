# app/services/jwt_service.py
import jwt
import secrets
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Union
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

class JWTService:
    """Сервис для работы с JWT токенами"""
    
    def __init__(self):
        # Для продакшена используем переменную окружения
        # Для разработки генерируем ключ один раз
        self.secret_key = os.getenv("JWT_SECRET_KEY")
        if not self.secret_key:
            # В режиме разработки создаем ключ
            self.secret_key = secrets.token_urlsafe(32)
            logger.warning(f"⚠️ JWT_SECRET_KEY не установлен, используется сгенерированный ключ")
        
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        self.refresh_token_expire_days = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    
    def create_access_token(
        self, 
        data: Dict, 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Создать access token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(
            to_encode, 
            self.secret_key, 
            algorithm=self.algorithm
        )
        return encoded_jwt
    
    def create_refresh_token(
        self,
        data: Dict,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Создать refresh token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            self.secret_key,
            algorithm=self.algorithm
        )
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict:
        """
        Проверить и декодировать токен
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
    
    def get_token_payload(self, token: str) -> Optional[Dict]:
        """
        Получить payload из токена без проверки expiration
        """
        try:
            # Используем опцию verify_exp=False для получения payload даже у истекшего токена
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False}
            )
            return payload
        except jwt.InvalidTokenError:
            return None

# Создаем глобальный экземпляр
jwt_service = JWTService()