from typing import Optional, Dict, Any
import jwt
import time
import os

class JWTHandler:
    """Handle JWT tokens"""
    
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET")
        if not self.secret_key and os.getenv("ENVIRONMENT") == "production":
            raise ValueError("JWT_SECRET environment variable is missing in production configuration!")
        self.secret_key = self.secret_key or "your-secret-key-change-in-production"
        self.algorithm = "HS256"
        self.access_token_expiry = 3600
        self.refresh_token_expiry = 2592000
    
    def create_access_token(self, user_id: str, tenant_id: str, roles: list = None) -> str:
        payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "roles": roles or ["user"],
            "type": "access",
            "iat": int(time.time()),
            "exp": int(time.time()) + self.access_token_expiry
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, user_id: str, tenant_id: str) -> str:
        payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "type": "refresh",
            "iat": int(time.time()),
            "exp": int(time.time()) + self.refresh_token_expiry
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except Exception:
            return None
    
    def verify_token(self, token: str) -> bool:
        return self.decode_token(token) is not None

jwt_handler = JWTHandler()
