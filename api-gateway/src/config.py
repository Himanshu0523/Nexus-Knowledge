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
        AUTH_REQUIRED: bool = True
        ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
        RATE_LIMIT_PER_MINUTE: int = 60
        CHAT_SERVICE_URL: str = "http://chat-service:8001"

        model_config = SettingsConfigDict(
            env_file=".env",
            case_sensitive=True,
            extra="ignore"
        )

except ImportError:
    try:
        from pydantic import BaseSettings
        
        class Settings(BaseSettings):
            APP_NAME: str = "Chatbot Platform API"
            VERSION: str = "1.0.0"
            API_PREFIX: str = "/api/v1"
            DEBUG: bool = False
            
            API_KEY: Optional[str] = "sk_dev_key_123456789"
            ADDITIONAL_API_KEYS: Optional[str] = "sk_test_key_1,sk_test_key_2"
            AUTH_REQUIRED: bool = True
            ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
            RATE_LIMIT_PER_MINUTE: int = 60
            CHAT_SERVICE_URL: str = "http://chat-service:8001"

            class Config:
                env_file = ".env"
                case_sensitive = True

    except ImportError:
        # Fallback dictionary settings if pydantic is unavailable
        import os
        class Settings:
            APP_NAME: str = os.getenv("APP_NAME", "Chatbot Platform API")
            VERSION: str = os.getenv("VERSION", "1.0.0")
            API_PREFIX: str = os.getenv("API_PREFIX", "/api/v1")
            DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
            
            API_KEY: Optional[str] = os.getenv("API_KEY", "sk_dev_key_123456789")
            ADDITIONAL_API_KEYS: Optional[str] = os.getenv("ADDITIONAL_API_KEYS", "sk_test_key_1,sk_test_key_2")
            AUTH_REQUIRED: bool = os.getenv("AUTH_REQUIRED", "true").lower() == "true"
            ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000")
            RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
            CHAT_SERVICE_URL: str = os.getenv("CHAT_SERVICE_URL", "http://chat-service:8001")

settings = Settings()