"""Run the RecipeBot Reddit command listener."""

import logging

from app.config.settings import get_settings
from app.reddit.listener import build_listener


def main() -> None:
    """Configure console logging and run the listener until interrupted."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()
    if not settings.bot_enabled:
        logging.getLogger(__name__).warning(
            "Reddit listener is disabled; set BOT_ENABLED=true after configuring credentials"
        )
        return
    build_listener(settings).run_forever()


if __name__ == "__main__":
    main()
