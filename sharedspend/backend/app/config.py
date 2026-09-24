from __future__ import annotations

from pathlib import Path
from typing import List

from sqlalchemy.engine import make_url
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./sharedspend.db"
    SECRET_KEY: str = "dev_secret_key_change_in_production"
    APP_ENV: str = "development"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def async_database_url(self) -> str:
        """Use SQLAlchemy's asyncpg dialect for standard PostgreSQL URLs."""
        if self.DATABASE_URL.startswith("postgres://"):
            return self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        parsed = make_url(self.DATABASE_URL)
        if (
            parsed.drivername.startswith("sqlite+")
            and parsed.database
            and parsed.database != ":memory:"
            and not Path(parsed.database).is_absolute()
        ):
            backend_dir = Path(__file__).resolve().parents[1]
            stable_path = (backend_dir / parsed.database).resolve()
            return parsed.set(database=str(stable_path)).render_as_string(hide_password=False)
        return self.DATABASE_URL

    @property
    def is_sqlite(self) -> bool:
        return self.async_database_url.startswith("sqlite+")

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
