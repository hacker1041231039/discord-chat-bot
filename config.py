"""
Configuration management for the Discord bot.
Uses Pydantic Settings for type-safe configuration with environment variable support.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Discord Configuration
    discord_token: str = Field(..., description="Discord Bot Token")
    discord_application_id: int = Field(..., description="Discord Application ID")
    discord_guild_id: int | None = Field(
        default=None, description="Guild ID for development command sync"
    )
    command_prefix: str = Field(default="!", description="Command prefix for text commands")

    # Bot Presence
    bot_status: str = Field(
        default="Chatting with users | /help", description="Bot status message"
    )

    # LLM Configuration
    llm_api_url: str = Field(
        default="https://api.example.com/v1/chat/completions",
        description="LLM API endpoint URL",
    )
    llm_api_key: str = Field(default="", description="LLM API Key")
    llm_model: str = Field(
        default="meta-llama/llama-3-8b-instruct", description="LLM model name"
    )
    llm_max_tokens: int = Field(default=2000, description="Maximum tokens per response")
    llm_temperature: float = Field(default=0.7, description="LLM temperature")
    llm_system_prompt: str = Field(
        default=(
            "You are a helpful, friendly, and engaging Discord chatbot. "
            "You respond naturally to users in a conversational manner. "
            "Keep responses concise but informative. "
            "You can use Discord markdown formatting when appropriate."
        ),
        description="System prompt for the LLM",
    )

    # Rate Limiting
    rate_limit_per_user: int = Field(
        default=30, description="Messages per minute per user"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/bot.log", description="Log file path")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @field_validator("llm_temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature range."""
        if not 0 <= v <= 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v

    @field_validator("llm_max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        """Validate max tokens."""
        if v <= 0 or v > 8192:
            raise ValueError("Max tokens must be between 1 and 8192")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()