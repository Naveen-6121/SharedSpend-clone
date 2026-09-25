from __future__ import annotations

from pathlib import Path
from typing import List
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url
from pydantic_settings import BaseSettings, SettingsConfigDict


_DEVELOPMENT_SECRET_KEY = "dev_secret_key_change_in_production"
_EXAMPLE_SECRET_KEY = "change_me_to_a_random_32_byte_hex_string"


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./sharedspend.db"
    SECRET_KEY: str = _DEVELOPMENT_SECRET_KEY
    APP_ENV: str = "development"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def __init__(self, **values):
        super().__init__(**values)
        self._validate_production_settings()

    def _validate_production_settings(self) -> None:
        if self.APP_ENV.lower() != "production":
            return

        if (
            self.SECRET_KEY in {_DEVELOPMENT_SECRET_KEY, _EXAMPLE_SECRET_KEY}
            or len(self.SECRET_KEY) < 32
        ):
            raise ValueError("production requires a SECRET_KEY of at least 32 characters")
        if not self.async_database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("production requires a PostgreSQL DATABASE_URL")

        origins = self.cors_origins_list
        if not origins or "*" in origins:
            raise ValueError("production CORS_ORIGINS must list explicit frontend origins")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme != "https"
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            ):
                raise ValueError("production CORS_ORIGINS must contain HTTPS site origins only")

    @property
    def async_database_url(self) -> str:
        """Normalize provider PostgreSQL URLs for SQLAlchemy's asyncpg driver."""
        parsed = make_url(self.DATABASE_URL)
        if parsed.drivername in {"postgres", "postgresql"}:
            parsed = parsed.set(drivername="postgresql+asyncpg")

        if parsed.drivername == "postgresql+asyncpg" and "sslmode" in parsed.query:
            query = dict(parsed.query)
            sslmode = query.pop("sslmode")
            if "ssl" in query and query["ssl"] != sslmode:
                raise ValueError("DATABASE_URL ssl and sslmode options conflict")
            query["ssl"] = sslmode
            parsed = parsed.set(query=query)

        if parsed.drivername == "postgresql+asyncpg" and "channel_binding" in parsed.query:
            # asyncpg currently does not implement libpq's channel_binding URL option.
            # TLS remains enforced when Neon supplies sslmode=require.
            query = dict(parsed.query)
            query.pop("channel_binding")
            parsed = parsed.set(query=query)

        if (
            parsed.drivername.startswith("sqlite+")
            and parsed.database
            and parsed.database != ":memory:"
            and not Path(parsed.database).is_absolute()
        ):
            backend_dir = Path(__file__).resolve().parents[1]
            stable_path = (backend_dir / parsed.database).resolve()
            return parsed.set(database=str(stable_path)).render_as_string(hide_password=False)
        if parsed.drivername == "postgresql+asyncpg":
            return parsed.render_as_string(hide_password=False)
        return self.DATABASE_URL

    @property
    def is_sqlite(self) -> bool:
        return self.async_database_url.startswith("sqlite+")

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
