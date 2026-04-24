from pydantic_settings import BaseSettings
import os
from typing import Optional

class Settings(BaseSettings):
    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    # JWT Authentication
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- UPDATED ---
    # Read the new SerpApi key
    SERPAPI_API_KEY: Optional[str] = None

    # Feature flags for the staged platform overhaul
    ENABLE_ASYNC_INGESTION: bool = False
    ENABLE_LOCAL_RANKER: bool = False
    ENABLE_FEEDBACK_RANKING: bool = False
    ENABLE_PERSONALIZED_REPORTS: bool = False

    # Classifier model controls
    ZERO_SHOT_MODEL_NAME: str = "facebook/bart-large-mnli"
    LOCAL_CLASSIFIER_MODEL_NAME: str = "valhalla/distilbart-mnli-12-1"
    CLASSIFIER_MAX_LABEL_TEXT_LENGTH: int = 512
    FULL_ARTICLE_MIN_CHARS: int = 300

    # Async infrastructure
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    ASYNC_INGESTION_TOPIC_BATCH_SIZE: int = 250
    INGESTION_MAX_ARTICLES_PER_TOPIC: int = 10
    INGESTION_PROGRESS_UPDATE_EVERY: int = 20

    # Runtime logging and network behavior
    SQLALCHEMY_ECHO: bool = False
    SCRAPER_TIMEOUT_SECONDS: int = 15

    class Config:
        # Load environment variables from the .env file
        # We assume .env is in the 'backend' folder,
        # one level up from this 'app' folder.
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        env_file_encoding = 'utf-8'

# Create one instance of the settings for our app to import
settings = Settings()