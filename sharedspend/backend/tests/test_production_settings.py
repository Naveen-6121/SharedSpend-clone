import pytest

from app.config import Settings


def production_settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://example.invalid/sharedspend",
        "SECRET_KEY": "s" * 48,
        "CORS_ORIGINS": "https://sharedspend.example.invalid",
    }
    values.update(overrides)
    return Settings(**values)


def test_valid_explicit_production_settings_are_accepted():
    settings = production_settings()

    assert settings.APP_ENV == "production"
    assert settings.CORS_ORIGINS == "https://sharedspend.example.invalid"


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
