"""Structural safety tests for development and Hemlock Compose files."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
DEVELOPMENT_COMPOSE = ROOT / "docker-compose.yml"
PRODUCTION_COMPOSE = ROOT / "docker-compose.prod.yml"
PRODUCTION_ENV = ROOT / ".env.example"
DEVELOPMENT_ENV = ROOT / ".env.development.example"
DEPLOY_DOC = ROOT / "docs" / "hemlock-deploy.md"
DOCKERFILE = ROOT / "Dockerfile"


def load_compose(path: Path) -> dict:
    """Load one repository-managed Compose configuration."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_both_compose_files_use_safe_postgres_port() -> None:
    """Postgres must publish only to loopback on configurable host port 55432."""
    expected_port = "127.0.0.1:${POSTGRES_HOST_PORT:-55432}:5432"

    for compose_path in (DEVELOPMENT_COMPOSE, PRODUCTION_COMPOSE):
        services = load_compose(compose_path)["services"]
        assert "postgres" in services
        assert services["postgres"]["ports"] == [expected_port]
        assert "5432:5432" not in services["postgres"]["ports"]


def test_database_clients_use_internal_postgres_service() -> None:
    """All app containers must connect through postgres:5432 without host gateways."""
    for compose_path in (DEVELOPMENT_COMPOSE, PRODUCTION_COMPOSE):
        services = load_compose(compose_path)["services"]
        for service_name in ("migrate", "web", "worker", "bot"):
            service = services[service_name]
            assert "postgres:5432" in service["environment"]["DATABASE_URL"]
            assert "host.docker.internal" not in str(service)


def test_production_web_is_loopback_only_and_artifacts_are_shared() -> None:
    """The proxy target must stay loopback-only while artifacts remain shared."""
    services = load_compose(PRODUCTION_COMPOSE)["services"]

    assert services["web"]["ports"] == ["127.0.0.1:8097:8000"]
    assert "./artifacts:/app/artifacts:ro" in services["web"]["volumes"]
    assert "./artifacts:/app/artifacts" in services["worker"]["volumes"]


def test_web_services_run_flask_with_gunicorn() -> None:
    """Both container stacks must serve the Flask factory through Gunicorn."""
    expected_command = [
        "gunicorn",
        "--bind",
        "0.0.0.0:8000",
        "app.web.server:create_app()",
    ]

    for compose_path in (DEVELOPMENT_COMPOSE, PRODUCTION_COMPOSE):
        web = load_compose(compose_path)["services"]["web"]
        assert web["command"] == expected_command
        assert web["environment"]["DEVVIT_INGESTION_ENABLED"].endswith(":-false}")
        assert web["environment"]["DEVVIT_WEBHOOK_SECRET"].endswith(":-}")
        assert web["environment"]["DEVVIT_REQUIRE_HMAC"].endswith(":-true}")
        assert web["environment"]["DEVVIT_SIGNATURE_TOLERANCE_SECONDS"].endswith(
            ":-300}"
        )


def test_bot_depends_on_compose_postgres() -> None:
    """The optional listener must wait for its Compose-managed database."""
    for compose_path in (DEVELOPMENT_COMPOSE, PRODUCTION_COMPOSE):
        bot = load_compose(compose_path)["services"]["bot"]
        assert bot["depends_on"]["postgres"]["condition"] == "service_healthy"


def test_environment_examples_use_container_database_and_safe_host_port() -> None:
    """Both environment examples should describe internal and host Postgres addresses."""
    for environment_path in (DEVELOPMENT_ENV, PRODUCTION_ENV):
        environment = environment_path.read_text(encoding="utf-8")
        assert "POSTGRES_HOST_PORT=55432" in environment
        assert "@postgres:5432/recipebot" in environment
        assert "host.docker.internal" not in environment
        assert "DEVVIT_INGESTION_ENABLED=false" in environment
        assert "DEVVIT_WEBHOOK_SECRET=" in environment
        assert "DEVVIT_REQUIRE_HMAC=true" in environment
        assert "DEVVIT_SIGNATURE_TOLERANCE_SECONDS=300" in environment

    production = PRODUCTION_ENV.read_text(encoding="utf-8")
    assert "ARTIFACT_ROOT=/app/artifacts" in production
    assert "ARTIFACT_BASE_URL=https://recipebot.devgw.com/cards" in production
    assert "WEB_HOST=0.0.0.0" in production
    assert "WEB_PORT=8000" in production
    assert "REDDIT_DRY_RUN=true" in production


def test_hemlock_runbook_uses_managed_postgres_without_host_changes() -> None:
    """Hemlock instructions must start Compose Postgres and leave host Postgres untouched."""
    runbook = DEPLOY_DOC.read_text(encoding="utf-8")

    assert "docker compose -f docker-compose.prod.yml up -d postgres" in runbook
    assert "proxy_pass http://127.0.0.1:8097;" in runbook
    assert "host.docker.internal" not in runbook
    assert "CREATE USER recipebot" not in runbook
    assert "host    recipebot" not in runbook
    assert "sudo mkdir -p artifacts/jobs" in runbook
    assert "sudo chown -R 10001:10001 artifacts" in runbook
    assert "sudo chmod -R u+rwX artifacts" in runbook


def test_runtime_image_installs_svg_rasterizer_and_imagemagick() -> None:
    """The shared worker/web image must include both rendering executables and fonts."""
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "librsvg2-bin" in dockerfile
    assert "imagemagick" in dockerfile
    assert "fonts-dejavu-core" in dockerfile
    assert "fonts-liberation" in dockerfile

    runbook = DEPLOY_DOC.read_text(encoding="utf-8")
    assert "build --no-cache worker web" in runbook
    assert "run --rm worker rsvg-convert --version" in runbook
