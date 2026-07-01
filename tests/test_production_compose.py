"""Structural safety tests for the Hemlock production Compose file."""

from pathlib import Path

import yaml

PRODUCTION_COMPOSE = Path(__file__).parents[1] / "docker-compose.prod.yml"
PRODUCTION_ENV = Path(__file__).parents[1] / ".env.example"
DEPLOY_DOC = Path(__file__).parents[1] / "docs" / "hemlock-deploy.md"


def load_production_compose() -> dict:
    """Load the repository-managed production Compose configuration."""
    return yaml.safe_load(PRODUCTION_COMPOSE.read_text(encoding="utf-8"))


def test_production_compose_has_no_postgres_service() -> None:
    """Production must never create a Compose-managed Postgres container."""
    services = load_production_compose()["services"]

    assert "postgres" not in services
    assert {"migrate", "web", "worker", "bot"}.issubset(services)


def test_production_database_services_use_host_gateway() -> None:
    """Every database client must resolve host Postgres through Docker's host gateway."""
    services = load_production_compose()["services"]

    for service_name in ("migrate", "web", "worker", "bot"):
        service = services[service_name]
        assert "host.docker.internal:host-gateway" in service["extra_hosts"]
        assert "host.docker.internal:5432" in service["environment"]["DATABASE_URL"]


def test_production_web_is_loopback_only_and_artifacts_are_shared() -> None:
    """The public proxy target must stay loopback-only while artifacts remain shared."""
    services = load_production_compose()["services"]

    assert services["web"]["ports"] == ["127.0.0.1:8097:8000"]
    assert "./artifacts:/app/artifacts:ro" in services["web"]["volumes"]
    assert "./artifacts:/app/artifacts" in services["worker"]["volumes"]


def test_production_environment_uses_hemlock_runtime_values() -> None:
    """The production example should target host Postgres and container-local paths."""
    environment = PRODUCTION_ENV.read_text(encoding="utf-8")

    assert "@host.docker.internal:5432/recipebot" in environment
    assert "ARTIFACT_ROOT=/app/artifacts" in environment
    assert "ARTIFACT_BASE_URL=https://recipebot.devgw.com/cards" in environment
    assert "WEB_HOST=0.0.0.0" in environment
    assert "WEB_PORT=8000" in environment
    assert "REDDIT_DRY_RUN=true" in environment


def test_hemlock_runbook_uses_only_production_compose() -> None:
    """Hemlock instructions must never start the development Postgres service."""
    runbook = DEPLOY_DOC.read_text(encoding="utf-8")

    assert "docker compose -f docker-compose.prod.yml" in runbook
    assert "docker compose up -d postgres" not in runbook
    assert "proxy_pass http://127.0.0.1:8097;" in runbook
