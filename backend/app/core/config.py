"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Prefer backend/.env over repo-root .env when both exist.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "MedExplain AI"
    environment: str = "development"
    # Comma-separated browser origins allowed for CORS (dev often uses 3000 and 3001).
    frontend_origin: str = "http://localhost:3000,http://localhost:3001"

    @property
    def cors_allow_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    # Database
    database_url: str = "postgresql://medexplain:medexplain@localhost:5432/medexplain"

    # Provider switches (provider-agnostic architecture)
    llm_provider: Literal["dashscope", "openai", "gemini", "offline"] = "dashscope"
    # tesseract = local/dev default; alibaba = cloud primary (stub until credentials)
    ocr_provider: Literal["alibaba", "tesseract"] = "tesseract"
    storage_provider: Literal["oss", "local"] = "local"

    # LLM / DashScope
    dashscope_api_key: str = ""
    dashscope_model: str = "qwen-turbo"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    gemini_api_key: str = ""

    # Alibaba Cloud OCR
    alibaba_ocr_access_key_id: str = ""
    alibaba_ocr_access_key_secret: str = ""
    alibaba_ocr_endpoint: str = "ocr-api.cn-hangzhou.aliyuncs.com"

    # Tesseract (local)
    tesseract_cmd: str = ""
    # Object storage — Alibaba OSS
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_endpoint: str = ""
    oss_bucket_name: str = ""
    oss_region: str = ""

    # Object storage — S3-compatible fallback
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_endpoint_url: str = ""
    s3_bucket_name: str = ""
    s3_region: str = "us-east-1"

    # Local storage (dev)
    local_storage_path: str = "./uploads"
    api_public_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
