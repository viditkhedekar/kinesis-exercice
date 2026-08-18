"""Settings resolution: Neon connection strings and storage backend selection."""
from __future__ import annotations

import pytest

from app.config import Settings


def _settings(**kwargs) -> Settings:
    # _env_file=None so a developer's local .env can't influence the assertions.
    return Settings(_env_file=None, **kwargs)


@pytest.mark.parametrize(
    "given",
    [
        # The three shapes Neon's dashboard hands out.
        "postgres://u:p@ep-cool-1.eu-central-1.aws.neon.tech/kinesis",
        "postgresql://u:p@ep-cool-1.eu-central-1.aws.neon.tech/kinesis",
        "postgresql+psycopg2://u:p@ep-cool-1.eu-central-1.aws.neon.tech/kinesis",
    ],
)
def test_neon_urls_normalize_to_the_psycopg2_dialect_with_tls(given):
    url = _settings(database_url=given).normalized_database_url()
    assert url.startswith("postgresql+psycopg2://")
    assert "sslmode=require" in url


def test_existing_query_params_and_sslmode_are_preserved():
    given = (
        "postgresql://u:p@ep-cool-1.aws.neon.tech/kinesis"
        "?sslmode=verify-full&channel_binding=require"
    )
    url = _settings(database_url=given).normalized_database_url()
    assert url.count("sslmode=") == 1
    assert "sslmode=verify-full" in url
    assert "channel_binding=require" in url


def test_neon_url_with_existing_params_gets_sslmode_appended_with_ampersand():
    given = "postgresql://u:p@ep-cool-1.aws.neon.tech/kinesis?application_name=x"
    url = _settings(database_url=given).normalized_database_url()
    assert url.endswith("?application_name=x&sslmode=require")


@pytest.mark.parametrize(
    "given",
    [
        "postgresql+psycopg2://kinesis:kinesis@localhost:5432/kinesis",
        "postgresql+psycopg2://kinesis:kinesis@postgres:5432/kinesis",  # docker-compose
        "postgresql+psycopg2://kinesis:kinesis@127.0.0.1:5432/kinesis",
    ],
)
def test_local_databases_are_not_forced_onto_tls(given):
    """Local Postgres has no TLS; forcing sslmode would break dev and compose."""
    assert "sslmode" not in _settings(database_url=given).normalized_database_url()


def test_sqlite_passes_through_untouched():
    assert _settings(database_url="sqlite://").normalized_database_url() == "sqlite://"


def test_storage_backend_auto_prefers_supabase_when_configured():
    s = _settings(supabase_url="https://p.supabase.co", supabase_service_role_key="k")
    assert s.supabase_configured()
    assert s.resolve_storage_backend() == "supabase"


def test_storage_backend_auto_falls_back_to_the_filesystem():
    s = _settings(supabase_url=None, supabase_service_role_key=None)
    assert not s.supabase_configured()
    assert s.resolve_storage_backend() == "filesystem"


def test_storage_backend_can_be_forced():
    s = _settings(
        storage_backend="filesystem",
        supabase_url="https://p.supabase.co",
        supabase_service_role_key="k",
    )
    assert s.resolve_storage_backend() == "filesystem"


def test_supabase_env_vars_are_read_without_the_kinesis_prefix(monkeypatch):
    """Supabase's own documented names work as-is (SUPABASE_URL, not KINESIS_...)."""
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "kinesis-media-prod")

    s = Settings(_env_file=None)

    assert s.supabase_url == "https://proj.supabase.co"
    assert s.supabase_service_role_key == "service-key"
    assert s.supabase_storage_bucket == "kinesis-media-prod"
    assert s.resolve_storage_backend() == "supabase"
