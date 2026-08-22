from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    
    class Settings(BaseSettings):
        APP_NAME: str = "Chatbot Platform API"
        VERSION: str = "1.0.0"
        API_PREFIX: str = "/api/v1"
        DEBUG: bool = False
        
        API_KEY: Optional[str] = "sk_dev_key_123456789"
        ADDITIONAL_API_KEYS: Optional[str] = "sk_test_key_1,sk_test_key_2"
        AUTH_REQUIRED: bool = False
        RATE_LIMIT_PER_MINUTE: int = 60
        CHAT_SERVICE_URL: str = "http://chat-service:8001"

        model_config = SettingsConfigDict(
            env_file=".env",
            case_sensitive=True,
            extra="ignore"
        )

except ImportError:
    from pydantic import BaseSettings
    
    class Settings(BaseSettings):
        APP_NAME: str = "Chatbot Platform API"
        VERSION: str = "1.0.0"
        API_PREFIX: str = "/api/v1"
        DEBUG: bool = False
        
        API_KEY: Optional[str] = "sk_dev_key_123456789"
        ADDITIONAL_API_KEYS: Optional[str] = "sk_test_key_1,sk_test_key_2"
        AUTH_REQUIRED: bool = False
        RATE_LIMIT_PER_MINUTE: int = 60
        CHAT_SERVICE_URL: str = "http://chat-service:8001"

        class Config:
            env_file = ".env"
            case_sensitive = True
            extra = "ignore"

settings = Settings()