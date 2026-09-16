from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="STORY_", extra="ignore")

    model_provider: str = "mock"
    model_name: str = "gpt-4o-mini"
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    qwen_api_key: SecretStr | None = Field(default=None, validation_alias="DASHSCOPE_API_KEY")
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    database_path: str = "story_weaver.db"
    max_npc_replies: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
