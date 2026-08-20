from typing import Dict, Any
import hashlib
import secrets

class APIKeyManager:
    """Manage API keys securely"""
    
    def __init__(self):
        self.key_prefix = "cb_live_"
        self.test_key_prefix = "cb_test_"
    
    def generate_key(self, prefix: str = None) -> tuple[str, str, str]:
        random_part = secrets.token_urlsafe(32)
        if prefix:
            full_key = f"{prefix}{random_part}"
        else:
            full_key = f"{self.key_prefix}{random_part}"
        
        key_hash = self.hash_key(full_key)
        key_prefix = full_key[:12] + "..."
        return full_key, key_hash, key_prefix
    
    def hash_key(self, api_key: str) -> str:
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def verify_key(self, api_key: str, stored_hash: str) -> bool:
        computed_hash = self.hash_key(api_key)
        return secrets.compare_digest(computed_hash, stored_hash)
    
    def extract_key_info(self, api_key: str) -> Dict[str, Any]:
        key_hash = self.hash_key(api_key)
        key_prefix = api_key[:12]
        return {
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "key_length": len(api_key),
            "is_test_key": api_key.startswith(self.test_key_prefix)
        }
    
    def validate_key_format(self, api_key: str) -> bool:
        if not api_key or len(api_key) < 20:
            return False
        return api_key.startswith(self.key_prefix) or api_key.startswith(self.test_key_prefix)

api_key_manager = APIKeyManager()
