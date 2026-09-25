import pytest

from app.config import Settings


def production_settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://example.invalid/sharedspend",
        "TEST_DATABASE_URL": None,
        "SECRET_KEY": "s" * 48,
        "CORS_ORIGINS": "https://sharedspend.example.invalid",
    }
    values.update(overrides)
    return Settings(**values)


def test_valid_explicit_production_settings_are_accepted():
    settings = production_settings()

    assert settings.APP_ENV == "production"
    assert settings.CORS_ORIGINS == "https://sharedspend.example.invalid"


def test_staging_uses_only_the_explicit_test_database_url():
    settings = Settings(
        _env_file=None,
        APP_ENV="staging",
        DATABASE_URL="postgresql://production-user:production-password@prod.example.invalid/sharedspend",
        TEST_DATABASE_URL="postgresql://test-user:test-password@test.example.invalid/sharedspend?sslmode=require",
    )

    assert settings.async_database_url.startswith("postgresql+asyncpg://test-user:")
    assert "test.example.invalid" in settings.async_database_url
    assert "prod.example.invalid" not in settings.async_database_url
    assert "test-password" not in repr(settings)
    assert "production-password" not in repr(settings)


def test_staging_loads_test_database_url_from_process_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://production-user:production-password@prod.example.invalid/sharedspend",
    )
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql://test-user:test-password@test.example.invalid/sharedspend?sslmode=require",
    )

    settings = Settings(_env_file=None)

    assert "test.example.invalid" in settings.async_database_url
    assert "prod.example.invalid" not in settings.async_database_url


def test_staging_requires_a_test_database_url_instead_of_falling_back():
    with pytest.raises(ValueError, match="staging requires TEST_DATABASE_URL"):
        Settings(_env_file=None, APP_ENV="staging", DATABASE_URL="postgresql://prod.invalid/db")


def test_test_database_url_cannot_be_set_in_production():
    with pytest.raises(ValueError, match="production must use DATABASE_URL"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            DATABASE_URL="postgresql://production.example.invalid/db",
            TEST_DATABASE_URL="postgresql://test.example.invalid/db",
            SECRET_KEY="s" * 48,
            CORS_ORIGINS="https://sharedspend.example.invalid",
        )


def test_development_keeps_using_sqlite_even_if_test_url_is_configured():
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        TEST_DATABASE_URL="postgresql://test-user:test-password@test.example.invalid/sharedspend?sslmode=require",
    )

    assert settings.is_sqlite
    assert settings.async_database_url == "sqlite+aiosqlite:///:memory:"


def test_development_rejects_postgresql_database_url():
    with pytest.raises(ValueError, match="development requires SQLite"):
        Settings(
            _env_file=None,
            APP_ENV="development",
            DATABASE_URL="postgresql://not-used.example.invalid/sharedspend",
        )


def test_render_https_origin_is_accepted_for_production_validation():
    settings = production_settings(CORS_ORIGINS="https://example.com")

    assert settings.cors_origins_list == ["https://example.com"]


def test_missing_production_cors_origin_fails_with_setup_guidance():
    with pytest.raises(ValueError, match="must be set to the frontend HTTPS origin"):
        production_settings(CORS_ORIGINS="")


@pytest.mark.parametrize(
    "overrides",
    [
        {"SECRET_KEY": "dev_secret_key_change_in_production"},
        {"SECRET_KEY": "change_me_to_a_random_32_byte_hex_string"},
        {"SECRET_KEY": "too-short"},
        {"DATABASE_URL": "sqlite+aiosqlite:///./sharedspend.db"},
        {"TEST_DATABASE_URL": "postgresql://test.example.invalid/sharedspend"},
        {"CORS_ORIGINS": "*"},
        {"CORS_ORIGINS": "http://localhost:5173"},
        {"CORS_ORIGINS": "https://localhost:5173"},
        {"CORS_ORIGINS": "https://sharedspend.example.invalid/path"},
    ],
)
def test_unsafe_or_incorrect_production_settings_are_rejected(overrides):
    with pytest.raises(ValueError):
        production_settings(**overrides)


def test_development_defaults_remain_available_for_local_sqlite():
    settings = Settings(_env_file=None)

    assert settings.APP_ENV == "development"
    assert settings.is_sqlite
    assert settings.cors_origins_list == ["http://localhost:5173"]


def test_production_configuration_error_does_not_echo_secrets_or_database_url():
    secret = "sensitive-test-value"
    database_url = "postgresql://private-user:private-password@private-host.invalid/db"

    with pytest.raises(ValueError) as error:
        production_settings(SECRET_KEY=secret, DATABASE_URL=database_url)

    assert secret not in str(error.value)
    assert database_url not in str(error.value)
