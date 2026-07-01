# RecipeBot

RecipeBot turns normalized recipes into portable SVG, PNG, and PDF cards. It includes Postgres-backed jobs, an ImageMagick renderer, ZIP bundles, a small Flask delivery service, exact-command ingestion from Reddit, and private-message result delivery. It does not use an external task queue.

## Requirements

- Python 3.12+
- ImageMagick (`magick` or configured equivalent) for PNG→PDF
- librsvg (`rsvg-convert` on your `PATH`) for SVG→PNG
- Docker, if you want to run the container stack

## Local development setup

Create a virtual environment and install the project with its development tools:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.development.example .env
```

Start Postgres and apply the migrations:

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg://recipebot:recipebot@127.0.0.1:55432/recipebot
alembic upgrade head
```

Configuration is loaded from environment variables or `.env`. Use `.env.development.example` locally; its `DATABASE_URL` is the address used inside Compose. Host-run tools and scripts should override it with the loopback URL shown above. `.env.example` contains the Hemlock production shape.

## Tests

```bash
pytest
```

## Sample render

```bash
python -m scripts.render_sample
```

The command writes `card.svg`, `card.png`, and `card.pdf` to `artifacts/sample-card/` and prints their absolute paths. Set `IMAGEMAGICK_BINARY` or `RSVG_CONVERT_BINARY` when either executable uses a nonstandard name or path.

## Durable job worker

With the local database URL exported during setup, apply migrations whenever the schema changes:

```bash
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

Flask is the web/API layer. The local script uses Flask's development server; Docker runs the same application factory with Gunicorn. The reserved `POST /internal/devvit/recipecard` endpoint remains unavailable by default (`DEVVIT_INGESTION_ENABLED=false`) and does not ingest requests yet.

Look up the completed job's `card_id` when needed:

```bash
psql "$DATABASE_URL" -c "SELECT id, card_id, status FROM jobs ORDER BY id DESC LIMIT 5;"
```

Then open `http://127.0.0.1:8000/cards/<card-id>` to preview the card and download each format or the ZIP bundle. The health endpoint is `http://127.0.0.1:8000/health`.

To run the single-process worker continuously instead, use:

```bash
python -m app.jobs.worker
```

Reddit-ingested jobs use the messaging lifecycle state for durable DM delivery before completion; synthetic jobs without a requester skip that step.

## Reddit command listener

RecipeBot recognizes only a standalone `!recipecard` comment. Extra text, flags, partial words, deleted comments, and comments authored by the configured bot account are ignored. Ingestion records the requesting username so the worker can privately deliver completed results.

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
REDDIT_DM_RESULTS=true
REDDIT_PUBLIC_FALLBACK_ON_DM_FAILURE=false
REDDIT_PUBLIC_ACK_ON_QUEUE=false
```

`ENABLED_SUBREDDITS` is the complete allowlist; the listener combines only those names into the PRAW comment stream. Start it locally after Postgres is running and migrations are applied:

```bash
python -m scripts.run_reddit_listener
```

`REDDIT_DRY_RUN=true` keeps all Reddit-side writes disabled while still allowing source, recipe, queued-job, artifact, and queued-message database records. Use a dedicated test account and controlled subreddit before setting it to `false` locally.

Completed Reddit jobs normally send the requester a private message containing the card landing page plus direct PNG, PDF, SVG, and ZIP links. Delivery attempts are stored in the `messages` table. A DM failure leaves the artifacts intact and fails the job unless `REDDIT_PUBLIC_FALLBACK_ON_DM_FAILURE=true`; with that explicit opt-in, RecipeBot replies to the original command with only the landing-page URL. The fallback is off by default.

`REDDIT_PUBLIC_ACK_ON_QUEUE=true` optionally posts a short acknowledgement when a new command is queued. It is also off by default. Neither delivery option changes command parsing or accepts per-command flags.

Password-flow script applications do not require manually selecting scopes in PRAW. For token-based configurations, private messages require the `privatemessages` scope, and the optional public reply/acknowledgement requires `submit`.

For a safe local delivery check:

1. Keep `REDDIT_DRY_RUN=true`, ingest a command, and run the worker. Confirm a `queued` DM record and generated artifacts.
2. Use a dedicated Reddit test account, set `REDDIT_DRY_RUN=false`, and leave public fallback disabled.
3. Run `python -m scripts.run_worker_once`, then inspect the `messages` row for `sent` or `failed` status.

## Development Docker runtime

Build the application image and start Postgres:

```bash
docker compose build
docker compose up postgres
```

In another terminal, start the web and worker services. Compose automatically runs migrations first:

```bash
docker compose up web worker
```

The web container listens on port `8000` internally and is published only at `127.0.0.1:8097`. Postgres remains internal at `postgres:5432` and is published for host tools only at `127.0.0.1:${POSTGRES_HOST_PORT:-55432}`. Worker and web containers share the host `./artifacts` directory. To create a demo job against the Compose database, run:

```bash
docker compose run --rm worker python -m scripts.create_sample_job
```

Open `http://127.0.0.1:8097/cards/<card-id>` after the worker completes it.

The Reddit listener is behind an explicit Compose profile and remains off during normal `docker compose up`. With the Reddit variables in `.env`, start it using:

```bash
docker compose --profile reddit up bot
```

These commands use `docker-compose.yml` and its development data volume. Use the production file on Hemlock.

## Hemlock production

Hemlock uses [docker-compose.prod.yml](docker-compose.prod.yml), including an isolated Postgres container, `migrate`, `web`, `worker`, and the optional profiled `bot`. Application containers connect through `postgres:5432`; host access is loopback-only on port `55432` by default, so Hemlock's existing Postgres on host port `5432` is unaffected.

The repeatable database, environment, deployment, and rollback-safe update procedure is documented in [docs/hemlock-deploy.md](docs/hemlock-deploy.md). The production web mapping is exactly `127.0.0.1:8097:8000`, leaving Nginx as the only public entry point.

The application image installs ImageMagick, deterministic fonts, and `librsvg2-bin`. SVG rasterization calls `rsvg-convert` directly; ImageMagick remains responsible for PDF generation.

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

Set `ARTIFACT_BASE_URL=https://recipebot.devgw.com/cards` so URLs written to `metadata.json` use the public hostname. Nginx remains host-managed and is never started or modified by Compose.
