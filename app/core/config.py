from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    APP_NAME: str = "AI Job Matching Server"
    DEBUG: bool = True

    DATABASE_URL: str

    GEMINI_API_KEY: str
    CV_AI_ENRICHMENT_ENABLED: bool = True

    JWT_ACCESS_SECRET: str
    JWT_ACCESS_EXPIRES_IN: str

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR / ".env.production"),
        extra="ignore",
    )

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_value(cls, value):
        if isinstance(value, bool):
            return value

        normalized = str(value or "").strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
            return False
        return value

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def sanitize_database_url(cls, value):
        raw = str(value or "").strip()
        if not raw:
            return raw

        # Some external tools append pgbouncer=true, which psycopg2 rejects.
        if "?" not in raw or "pgbouncer" not in raw.lower():
            return raw

        base, query = raw.split("?", 1)
        kept_parts: list[str] = []
        for part in query.split("&"):
            key = part.split("=", 1)[0].strip().lower()
            if key == "pgbouncer":
                continue
            if part.strip():
                kept_parts.append(part.strip())

        return f"{base}?{'&'.join(kept_parts)}" if kept_parts else base


settings = Settings()
