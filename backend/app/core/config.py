import os
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    PROJECT_NAME: str = "DataFlow Enterprise"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dataflow-enterprise-super-secret-key-32bytes-secure!")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "bGFyZ2Utc2VjdXJlLWtleS0zMi1ieXRlcy1mb3ItZmVybmV0ISE=")

    # Database configuration (Defaults to PostgreSQL or SQLite fallback for portable dev)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite:///./dataflow_metadata.db"
    )

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000"
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
