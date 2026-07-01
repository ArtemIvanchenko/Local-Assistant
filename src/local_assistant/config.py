"""Typed configuration loaded from environment / .env.

Single source of truth for model choices, paths, and behaviour thresholds so they
can be tuned without touching code (see plan: "всё в одном конфиге").
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Telegram
    telegram_bot_token: str = ""
    owner_chat_ids: str = ""  # comma-separated; only these ids are served

    # Ollama / models
    ollama_host: str = "http://127.0.0.1:11434"
    model_main: str = "qwen3.5:4b"
    model_main_fallback: str = "qwen3:4b-instruct"
    model_router: str = "qwen3:1.7b"
    model_embed: str = "embeddinggemma:300m"
    model_draft: str = "qwen3:0.6b"
    ollama_speculative_decode: bool = False

    # Context / inference (see docs/architecture.md — capacity != working point)
    num_ctx: int = 8192
    working_context_budget: int = 4096
    kv_cache_type: str = "q8_0"
    num_threads: int = 4

    # Storage
    db_path: str = "./data/assistant.db"
    memory_md_path: str = "./data/MEMORY.md"
    doc_inbox_dir: str = "./docs/inbox"
    backup_dir: str = "./backups"

    # Web search (ddgs)
    search_region: str = "ru-ru"
    search_max_results: int = 5

    # Apple / iCloud (CalDAV calendar+reminders, CardDAV contacts).
    # Use an app-specific password from appleid.apple.com (NOT your Apple ID password).
    apple_id: str = ""
    apple_app_password: str = ""
    icloud_caldav_url: str = "https://caldav.icloud.com/"
    icloud_carddav_url: str = "https://contacts.icloud.com/"
    icloud_calendar_name: str = ""   # blank = first calendar that supports events
    icloud_reminders_list: str = ""  # blank = first list that supports VTODO
    icloud_sync_minutes: int = 15

    # Behaviour
    timezone: str = "Europe/Moscow"
    morning_digest: str = "08:00"
    evening_digest: str = "21:00"
    nightly_reflection: str = "03:00"
    quiet_hours: str = "22:30-07:30"
    max_proactive_per_day: int = 4

    @property
    def owner_ids(self) -> list[int]:
        return [int(x) for x in self.owner_chat_ids.split(",") if x.strip()]

    @property
    def icloud_enabled(self) -> bool:
        return bool(self.apple_id and self.apple_app_password)


settings = Settings()
