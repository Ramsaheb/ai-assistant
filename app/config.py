import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables with validation."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    MONDAY_API_TOKEN: str = Field(..., description="Monday.com API token")
    DEALS_BOARD_ID: str = Field(..., description="Board ID for deals")
    WORK_ORDERS_BOARD_ID: str = Field(default="", description="Board ID for work orders")
    GROQ_API_KEY: str = Field(..., description="Groq LLM API key")

    MONDAY_API_URL: str = "https://api.monday.com/v2"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_TEMPERATURE: float = 0.3
    REQUEST_TIMEOUT: int = 30


try:
    settings = Settings()
except Exception as e:
    raise RuntimeError(
        f"Missing required environment variables. "
        f"Copy .env.example to .env and fill in values. Error: {e}"
    )