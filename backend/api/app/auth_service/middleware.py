from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

class AuthMiddleware:
    """Middleware для проверки аутентификации"""
    
    def __init__(self, jwt_service):
        self.jwt_service = jwt_service
        self.public_paths = {
            "/auth/login",
            "/auth/register",
            "/auth/refresh",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json"
        }
    
    async def __call__(self, request: Request, call_next):
        if request.url.path in self.public_paths or request.url.path.startswith("/docs"):
            return await call_next(request)
        
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Not authenticated"}
            )
        
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid authentication header format"}
            )
        
        token = parts[1]
        
        try:
            payload = self.jwt_service.verify_token(token)
            
            if payload.get("type") != "access":
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid token type"}
                )
            
            request.state.user = {
                "username": payload.get("sub"),
                "user_id": payload.get("user_id"),
                "full_name": payload.get("full_name", ""),
                "role": payload.get("role", "user")
            }
            
        except ValueError as e:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": str(e)}
            )
        except Exception as e:
            logger.error(f"Unexpected error during auth: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )
        
        return await call_next(request)