"""Run the local RecipeBot FastAPI delivery service."""

import uvicorn

from app.config.settings import get_settings


def main() -> None:
    """Start Uvicorn with the configured local host and port."""
    settings = get_settings()
    uvicorn.run("app.web.server:app", host=settings.web_host, port=settings.web_port)


if __name__ == "__main__":
    main()
