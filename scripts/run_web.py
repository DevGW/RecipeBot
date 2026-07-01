"""Run the local RecipeBot Flask delivery service."""

from app.config.settings import get_settings
from app.web.server import create_app


def main() -> None:
    """Start Flask's local server with the configured host and port."""
    settings = get_settings()
    create_app(settings).run(host=settings.web_host, port=settings.web_port)


if __name__ == "__main__":
    main()
