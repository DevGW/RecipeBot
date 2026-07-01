# RecipeBot

RecipeBot turns normalized recipes into portable SVG, PNG, and PDF cards. It includes Postgres-backed jobs, an ImageMagick renderer, ZIP bundles, a small FastAPI delivery service, and exact-command ingestion from Reddit. It does not send Reddit replies or DMs and does not use an external task queue.

## Requirements

- Python 3.12+
- ImageMagick 7 (`magick` on your `PATH`)
- Docker, if you want to run the container stack

## Setup

Create a virtual environment and install the project with its development tools:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Start Postgres and apply the migrations:

```bash
docker compose up -d postgres
alembic upgrade head
```

Configuration is loaded from environment variables or `.env`; see `.env.example` for all supported values.

## Tests

```bash
pytest
```

## Sample render

```bash
python -m scripts.render_sample
```

The command writes `card.svg`, `card.png`, and `card.pdf` to `artifacts/sample-card/` and prints their absolute paths. Set `IMAGEMAGICK_BINARY` if ImageMagick is installed under a different executable name.

## Durable job worker

Start Postgres and apply all migrations:

```bash
docker compose up -d postgres
alembic upgrade head
```

Create a synthetic queued job, then process one queue item:

```bash
python -m scripts.create_sample_job
python -m scripts.run_worker_once
```

The first command prints the new job id. The worker claims that job with Postgres row locking and writes `card.svg`, `card.png`, `card.pdf`, `metadata.json`, and `recipe-card.zip` beneath `artifacts/jobs/<job-id>/`.

Start the local delivery service in another terminal:

```bash
python -m scripts.run_web
```

Look up the completed job's `card_id` when needed:

```bash
psql "$DATABASE_URL" -c "SELECT id, card_id, status FROM jobs ORDER BY id DESC LIMIT 5;"
```

Then open `http://127.0.0.1:8000/cards/<card-id>` to preview the card and download each format or the ZIP bundle. The health endpoint is `http://127.0.0.1:8000/health`.

To run the single-process worker continuously instead, use:

```bash
python -m app.jobs.worker
```

The messaging lifecycle state is reserved for later delivery behavior.

## Reddit command listener

RecipeBot recognizes only a standalone `!recipecard` comment. Extra text, flags, partial words, deleted comments, and comments authored by the configured bot account are ignored. Ingestion creates a Postgres job; it does not reply publicly or send a DM.

RecipeBot is an external PRAW bot, so Reddit API access and a traditional script-app credential are required. Review Reddit's [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy), request access if required, and create a script application from [Reddit app preferences](https://www.reddit.com/prefs/apps). PRAW's [password-flow documentation](https://praw.readthedocs.io/en/stable/getting_started/authentication.html) explains the client id, secret, username, and password fields.

Set the listener configuration in `.env`:

```dotenv
BOT_ENABLED=true
ENABLED_SUBREDDITS=recipes,cooking
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USERNAME=your_bot_username
REDDIT_PASSWORD=your_bot_password
REDDIT_USER_AGENT=RecipeBot/0.1 by u/your_bot_username
REDDIT_COMMAND=!recipecard
REDDIT_DRY_RUN=true
```

`ENABLED_SUBREDDITS` is the complete allowlist; the listener combines only those names into the PRAW comment stream. Start it locally after Postgres is running and migrations are applied:

```bash
python -m scripts.run_reddit_listener
```

`REDDIT_DRY_RUN=true` keeps all Reddit-side writes disabled while still allowing source, recipe, and queued-job database records. This release has no Reddit write operations even when dry-run mode is false: no replies and no DMs are implemented.

## Docker runtime

Build the application image and start Postgres:

```bash
docker compose build
docker compose up postgres
```

In another terminal, start the web and worker services. Compose automatically runs migrations first:

```bash
docker compose up web worker
```

The web container listens on port `8000` internally and is published only at `127.0.0.1:8097`. Worker and web containers share the host `./artifacts` directory. To create a demo job against the Compose database, run:

```bash
docker compose run --rm worker python -m scripts.create_sample_job
```

Open `http://127.0.0.1:8097/cards/<card-id>` after the worker completes it.

The Reddit listener is behind an explicit Compose profile and remains off during normal `docker compose up`. With the Reddit variables in `.env`, start it using:

```bash
docker compose --profile reddit up bot
```

## Hemlock / Nginx reverse proxy

Configure the Hemlock route with:

```text
Host: recipebot.devgw.com
Target: http://127.0.0.1:8097
```

The equivalent Nginx server block is:

```nginx
server {
    listen 443 ssl;
    server_name recipebot.devgw.com;

    location / {
        proxy_pass http://127.0.0.1:8097;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Set `ARTIFACT_BASE_URL=https://recipebot.devgw.com/cards` so URLs written to `metadata.json` use the public hostname. Web authentication and Reddit delivery behavior are intentionally not implemented yet.
