from fastapi import HTTPException, Header, Request
from typing import Optional
import os
import time
import hashlib
import hmac
from datetime import datetime, timedelta

class APIKeyManager:
    """Simple API key manager for Phase 1"""
    
    def __init__(self):
        self.api_key = os.getenv("API_KEY", None)
        self.api_keys = self._load_api_keys()
        
    def _load_api_keys(self) -> dict:
        """Load API keys from environment or config"""
        keys = {}
        
        # Primary API key
        if self.api_key:
            keys[self.api_key] = {
                "name": "default",
                "created_at": datetime.utcnow(),
                "is_active": True
            }
        
        # Additional keys could be loaded from a file or database
        # For Phase 1, we'll support comma-separated keys in env
        additional_keys = os.getenv("ADDITIONAL_API_KEYS", "")
        if additional_keys:
            for key in additional_keys.split(","):
                if key.strip():
                    keys[key.strip()] = {
                        "name": f"additional_{len(keys)}",
                        "created_at": datetime.utcnow(),
                        "is_active": True
                    }
        
        return keys
    
    def validate_key(self, api_key: str) -> bool:
        """Validate an API key"""
        if not api_key:
            return False
        
        key_info = self.api_keys.get(api_key)
        return key_info is not None and key_info.get("is_active", False)
    
    def get_key_info(self, api_key: str) -> Optional[dict]:
        """Get information about an API key"""
        return self.api_keys.get(api_key)

# Initialize key manager
key_manager = APIKeyManager()

async def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, description="API key for authentication"),
    authorization: Optional[str] = Header(None, description="Bearer token for authentication")
) -> Optional[str]:
    """
    Verify API key or JWT token for authentication.
    Extracts authenticated user_id and tenant_id into request.state.
    """
    auth_required = os.getenv("AUTH_REQUIRED", "true").lower() == "true"
    
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
    
    # First try JWT authentication
    if token:
        from security.jwt_handler import jwt_handler
        payload = jwt_handler.decode_token(token)
        if payload:
            request.state.user_id = payload.get("sub")
            request.state.tenant_id = payload.get("tenant_id")
            request.state.roles = payload.get("roles", [])
            return token

    # Fallback to API Key
    api_key = x_api_key or token
    if api_key and key_manager.validate_key(api_key):
        request.state.user_id = "api_key_user"
        request.state.tenant_id = "default_tenant"
        return api_key
    
    if not auth_required:
        request.state.user_id = getattr(request.state, "user_id", "anonymous")
        request.state.tenant_id = getattr(request.state, "tenant_id", "default_tenant")
        return None

    raise HTTPException(
        status_code=401,
        detail={
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Valid Authentication token or API key is required",
                "request_id": getattr(request.state, "request_id", None)
            }
        }
    )

async def verify_api_key_optional(
    request: Request,
    x_api_key: Optional[str] = Header(None, description="API key for authentication")
) -> Optional[str]:
    """
    Optional API key verification - doesn't fail if key is missing
    Useful for endpoints that work with or without authentication
    """
    if not key_manager.api_keys:
        return None
    
    if x_api_key and key_manager.validate_key(x_api_key):
        return x_api_key
    
    return None

def generate_api_key() -> str:
    """Generate a new API key (useful for admin endpoints)"""
    import secrets
    return f"sk_{secrets.token_urlsafe(32)}"

def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage (best practice)"""
    return hashlib.sha256(api_key.encode()).hexdigest()