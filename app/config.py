"""Application settings for the Indian QoL Concierge."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Indian QoL Concierge"
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    BASE_URL: str = Field(default="http://localhost:8000")
    INTERNAL_TICK_SECRET: str = Field(default="nexus-tick-secret")

    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile")

    # Conversational agent brain. "auto" = Gemini then Groq. Use "ollama" for local rehearsal.
    LLM_PROVIDER: Literal["auto", "gemini", "groq", "ollama"] = Field(default="auto")
    GEMINI_API_KEY: str = Field(default="")
    # Cheap tool-loop default; override with GEMINI_MODEL=gemini-3.6-flash if needed.
    GEMINI_MODEL: str = Field(default="gemini-3.5-flash-lite")

    OLLAMA_BASE_URL: str = Field(default="http://127.0.0.1:11434")
    OLLAMA_MODEL: str = Field(default="qwen2.5:7b-instruct")

    DATABASE_URL: str = Field(default="sqlite:///./nexus_memory.db")

    USE_MOCK_MCP: bool = Field(default=True)
    LOCAL_MCP_BASE: str = Field(default="http://127.0.0.1:8000")
    SWIGGY_FOOD_ENDPOINT: str = Field(default="https://mcp.swiggy.com/food")
    SWIGGY_IM_ENDPOINT: str = Field(default="https://mcp.swiggy.com/im")
    SWIGGY_DINEOUT_ENDPOINT: str = Field(default="https://mcp.swiggy.com/dineout")
    SWIGGY_OAUTH_TOKEN: str = Field(default="")
    SWIGGY_CLIENT_ID: str = Field(default="")
    SWIGGY_CLIENT_SECRET: str = Field(default="")

    GOOGLE_CALENDAR_CREDENTIALS_PATH: str = Field(default="credentials/google_credentials.json")
    GOOGLE_CALENDAR_TOKEN_PATH: str = Field(default="credentials/google_token.json")
    GOOGLE_PUBSUB_VERIFICATION_TOKEN: str = Field(default="nexus-pubsub-secret-token")
    PRIMARY_CALENDAR_ID: str = Field(default="primary")
    # False = night-out fails loudly when OAuth is dead (preferred for real demos).
    # Tests / offline CI can set GOOGLE_CALENDAR_ALLOW_MOCK=true.
    GOOGLE_CALENDAR_ALLOW_MOCK: bool = Field(default=False)

    NOTIFICATION_PLATFORM: Literal["discord", "telegram", "slack", "console"] = Field(
        default="console"
    )
    DISCORD_WEBHOOK_URL: str = Field(default="")
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_CHAT_ID: str = Field(default="")
    # False = force console for unsolicited Telegram HITL/QoL pushes (inbound replies stay active).
    TELEGRAM_OUTBOUND_ENABLED: bool = Field(default=True)
    SLACK_WEBHOOK_URL: str = Field(default="")

    OPENWEATHER_API_KEY: str = Field(default="")
    FORCE_SCENARIO_WEATHER: bool = Field(default=False)
    FORCE_FUEL_GUARD: bool = Field(default=False)
    HOME_CITY: str = Field(default="Pune")
    HOME_LAT: float = Field(default=18.5204)
    HOME_LNG: float = Field(default=73.8567)
    DEFAULT_ADDRESS_ID: str = Field(
        default="addr_kp_001",
        description="Mock-only fallback address. Live mode must use get_addresses.",
    )


settings = Settings()
