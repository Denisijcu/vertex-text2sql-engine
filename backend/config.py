from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    RAW_DATA_PATH: str = "dataset/raw/spider_sample.json"
    PROCESSED_DATA_PATH: str = "dataset/processed/train_text2sql.jsonl"
    LOG_LEVEL: str = "INFO"
    MAX_TOKENS_LIMIT: int = 2048

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()