import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Techity AI Research Assistant"
    API_V1_STR: str = "/v1"
    
    # Security
    SECRET_KEY: str = "supersecretsecuritykeypleasechangeinproduction12345"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Databases
    DATABASE_URL: str = "sqlite:///./techity.db"
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"
    
    # LLM Settings
    DEFAULT_LLM_PROVIDER: str = "gemini"  # "gemini" or "openai"
    
    # API Keys (optional if passed via front-end, but loaded from environment if present)
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # Models
    GEMINI_LLM_MODEL: str = "gemini-1.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"
    
    OPENAI_LLM_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
