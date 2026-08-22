import os
from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    
    class Settings(BaseSettings):
        APP_NAME: str = "Chat Service"
        VERSION: str = "3.0.0"
        API_PREFIX: str = "/api/v1"
        DEBUG: bool = False
        
        DATABASE_URL: str = "postgresql://chatbot:chatbot_password@postgres:5432/chatbot_db"
        REDIS_HOST: str = "redis"
        REDIS_PORT: int = 6379
        QDRANT_HOST: str = "qdrant"
        QDRANT_PORT: int = 6333
        QDRANT_COLLECTION: str = "document_chunks"
        EMBEDDING_DIM: int = 384
        LLM_PROVIDER: str = "mock"
        EMBEDDING_MODEL: str = "mock"
        KAFKA_BOOTSTRAP_SERVERS: str = "kafka:29092"

        model_config = SettingsConfigDict(
            env_file=".env",
            case_sensitive=True,
            extra="ignore"
        )

except ImportError:
    try:
        from pydantic import BaseSettings
        
        class Settings(BaseSettings):
            APP_NAME: str = "Chat Service"
            VERSION: str = "3.0.0"
            API_PREFIX: str = "/api/v1"
            DEBUG: bool = False
            
            DATABASE_URL: str = "postgresql://chatbot:chatbot_password@postgres:5432/chatbot_db"
            REDIS_HOST: str = "redis"
            REDIS_PORT: int = 6379
            QDRANT_HOST: str = "qdrant"
            QDRANT_PORT: int = 6333
            QDRANT_COLLECTION: str = "document_chunks"
            EMBEDDING_DIM: int = 384
            LLM_PROVIDER: str = "mock"
            EMBEDDING_MODEL: str = "mock"
            KAFKA_BOOTSTRAP_SERVERS: str = "kafka:29092"

            class Config:
                env_file = ".env"
                case_sensitive = True

    except ImportError:
        class Settings:
            APP_NAME: str = os.getenv("APP_NAME", "Chat Service")
            VERSION: str = os.getenv("VERSION", "3.0.0")
            API_PREFIX: str = os.getenv("API_PREFIX", "/api/v1")
            DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
            
            DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://chatbot:chatbot_password@postgres:5432/chatbot_db")
            REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
            REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
            QDRANT_HOST: str = os.getenv("QDRANT_HOST", "qdrant")
            QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
            QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "document_chunks")
            EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "384"))
            LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")
            EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "mock")
            KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")

settings = Settings()
