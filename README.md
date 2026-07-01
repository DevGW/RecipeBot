# RecipeBot

RecipeBot turns normalized recipes into portable recipe-card artifact bundles.

It generates:

- SVG
- PNG
- PDF
- metadata JSON
- ZIP bundles

RecipeBot includes:

- Postgres-backed durable jobs
- deterministic SVG rendering
- `rsvg-convert` SVG-to-PNG rasterization
- ImageMagick PDF generation
- a Flask/Gunicorn delivery and ingestion service
- a Docker Compose runtime
- a Devvit server-only Reddit adapter for exact `!recipecard` command ingestion
- an optional legacy PRAW listener retained for external-bot experiments

RecipeBot does not use an external task queue. Postgres is the durable queue.

The preferred Reddit integration is Devvit. The Devvit adapter listens for comment-created events, detects the exact standalone `!recipecard` command, resolves the parent recipe post or comment, signs the payload, and sends it to the Flask backend.

The Devvit adapter does **not** render cards, store recipes inside Devvit, send DMs, or post public Reddit replies. Rendering, persistence, artifact generation, and artifact hosting are handled by the Flask/Postgres/worker backend.

The legacy PRAW listener is retained as an optional adapter but is no longer the preferred path.

## Architecture

```text
Reddit / Devvit
  onCommentCreate trigger
  exact !recipecard detection
  parent post/comment resolution
  signed POST to Flask backend

Backend runtime
  Flask/Gunicorn API
  Postgres
  worker
  ImageMagick/rsvg renderer
  artifact hosting

Public reverse proxy
  HTTPS frontend
  forwards to Flask/Gunicorn
```

Devvit does not run inside the backend container stack. Devvit runs through Reddit's Devvit runtime after upload or playtest. The container stack runs the Flask/Postgres/worker/artifact backend.

## Requirements

- Python 3.12+
- Postgres
- ImageMagick, using `magick` or a configured equivalent
- `librsvg`, using `rsvg-convert`
- Docker and Docker Compose
- Node.js for the Devvit adapter

## Local development setup

Create a virtual environment and install the project with development tools:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.development.example .env
```

Start Postgres and apply migrations:

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg://recipebot:recipebot@127.0.0.1:55432/recipebot
alembic upgrade head
```

Configuration is loaded from environment variables or `.env`.

Use `.env.development.example` locally. Host-run tools and scripts should use the loopback database URL shown above.

`.env.example` documents the production-style environment shape.

## Tests

```bash
pytest
```

## Sample render

```bash
python -m scripts.render_sample
```

The command writes:

```text
artifacts/sample-card/card.svg
artifacts/sample-card/card.png
artifacts/sample-card/card.pdf
```

Set `IMAGEMAGICK_BINARY` or `RSVG_CONVERT_BINARY` when either executable uses a nonstandard name or path.

## Durable job worker

Apply migrations whenever the schema changes:

```bash
alembic upgrade head
```

Create a synthetic queued job, then process one queue item:

```bash
python -m scripts.create_sample_job
python -m scripts.run_worker_once
```

The first command prints the new job ID.

The worker claims that job with Postgres row locking and writes the completed artifact bundle beneath:

```text
artifacts/jobs/<job-id>/
```

Generated files include:

```text
card.svg
card.png
card.pdf
metadata.json
recipe-card.zip
```

To run the worker continuously:

```bash
python -m app.jobs.worker
```

Synthetic jobs without a requester skip messaging.

Legacy PRAW-ingested jobs can use the messaging lifecycle state for durable DM delivery before completion. Devvit-ingested jobs currently queue silently and do not send DMs or public replies.

## Local delivery service

Start the local delivery service in another terminal:

```bash
python -m scripts.run_web
```

Flask is the web/API layer. The local script uses Flask's development server. Docker runs the same application factory with Gunicorn.

Look up the completed job's `card_id` when needed:

```bash
psql "$DATABASE_URL" -c "SELECT id, card_id, status FROM jobs ORDER BY id DESC LIMIT 5;"
```

Then open:

```text
http://127.0.0.1:8000/cards/<card-id>
```

The card page links to the generated SVG, PNG, PDF, metadata, and ZIP bundle.

The local health endpoint is:

```text
http://127.0.0.1:8000/health
```

## Public policy pages

The Flask web service exposes public policy pages for Devvit app review and user transparency:

```text
/terms
/privacy
```

These pages should remain unauthenticated and should not include tracking, analytics, cookies, or external assets.

In production, configure the Devvit app details with the deployed public URLs:

```text
https://<PUBLIC_BACKEND_DOMAIN>/terms
https://<PUBLIC_BACKEND_DOMAIN>/privacy
```

## Devvit ingestion

Devvit is the preferred Reddit adapter.

When the Devvit app detects an exact standalone `!recipecard` command, it sends normalized source data to the Flask backend:

```text
POST /internal/devvit/recipecard
```

Production URL shape:

```text
https://<PUBLIC_BACKEND_DOMAIN>/internal/devvit/recipecard
```

Enable the endpoint and configure a strong shared secret in the web service environment:

```bash
DEVVIT_INGESTION_ENABLED=true
DEVVIT_WEBHOOK_SECRET=replace_with_a_long_random_secret
DEVVIT_REQUIRE_HMAC=true
DEVVIT_SIGNATURE_TOLERANCE_SECONDS=300
```

The endpoint is hidden with a `404` while disabled.

With HMAC required, the Devvit app must send:

```text
X-RecipeBot-Timestamp
X-RecipeBot-Signature
```

`X-RecipeBot-Timestamp` is Unix seconds.

`X-RecipeBot-Signature` is lowercase hexadecimal HMAC SHA-256.

The signed bytes are exactly:

```text
timestamp + "." + raw_request_body
```

The signature key is:

```text
DEVVIT_WEBHOOK_SECRET
```

RecipeBot compares signatures in constant time and rejects requests outside the configured timestamp window.

Example payload:

```json
{
  "command_comment_id": "t1_command",
  "requester_username": "example_user",
  "subreddit": "recipes",
  "source_type": "comment",
  "source_fullname": "t1_parent",
  "source_title": "Optional title",
  "source_body": "Ingredients:\n- bread\nDirections:\n1. Toast.",
  "source_permalink": "https://www.reddit.com/...",
  "source_url": "https://www.reddit.com/...",
  "created_utc": 1780000000
}
```

Valid requests use the deterministic extractor and existing Postgres job service. Repeated `command_comment_id` values return the existing job instead of creating duplicates.

Keep this enabled in production:

```bash
DEVVIT_REQUIRE_HMAC=true
```

The shared secret must be configured identically in RecipeBot and the Devvit app. It must not be committed or logged.

The server-only TypeScript Devvit adapter and its playtest instructions live in:

```text
devvit/
```

## Devvit fetch-domain approval

The Devvit adapter uses HTTP Fetch to call the backend domain.

`devvit/devvit.json` must use the exact hostname only:

```json
{
  "permissions": {
    "http": {
      "enable": true,
      "domains": ["<PUBLIC_BACKEND_DOMAIN>"]
    },
    "reddit": true
  }
}
```

Do not use:

```text
https://<PUBLIC_BACKEND_DOMAIN>
<PUBLIC_BACKEND_DOMAIN>/internal/devvit/recipecard
*.example.com
```

The domain exception is reviewed by Reddit. Until it is approved, playtest logs may show:

```text
HTTP request to domain: <PUBLIC_BACKEND_DOMAIN> is not allowed
```

That means the Devvit trigger, Hono server, command detection, and backend request construction are working, but Reddit is blocking the outbound fetch before it reaches Flask.

Check the domain status in the Reddit Developer Portal under the app's Developer Settings.

The app should also have Terms and Privacy Policy links configured in the Reddit Developer Portal app details.

## Devvit server runtime

The Devvit app is a server-only Devvit Web app.

The server entry in `devvit/devvit.json` should be:

```json
{
  "server": {
    "entry": "dist/server/index.cjs"
  }
}
```

The server bundle must be CommonJS.

The Hono app should be started through the Devvit Web server runtime, not only exported for tests.

Expected runtime shape:

```ts
import { serve } from "@hono/node-server";
import { createServer, getServerPort } from "@devvit/web/server";
import { app } from "./app";

serve({
  fetch: app.fetch,
  createServer,
  port: getServerPort(),
});
```

Tests should import the Hono app directly and must not start the real server.

## Devvit local setup

From the repository root:

```bash
cd devvit
npm install
```

Authenticate the Devvit CLI:

```bash
npx devvit login
```

Verify login:

```bash
npx devvit whoami
```

## Devvit settings

Configure the backend URL:

```bash
npx devvit settings set RECIPEBOT_BACKEND_URL
```

Use the deployed backend origin:

```text
https://<PUBLIC_BACKEND_DOMAIN>
```

Configure the webhook secret:

```bash
npx devvit settings set RECIPEBOT_WEBHOOK_SECRET
```

Use the same value as the backend's `DEVVIT_WEBHOOK_SECRET`.

Do not paste the secret into commits, screenshots, logs, README files, or issue reports.

## Devvit test and build

From `devvit/`:

```bash
npm test
npm run typecheck
npm run build
```

Useful bundle checks:

```bash
grep -R "RecipeBot onCommentCreate handler entered" -n dist/server/index.cjs
grep -R "RecipeBot checking comment command" -n dist/server/index.cjs
grep -R "RecipeBot backend request" -n dist/server/index.cjs
grep -R "serve({" -n dist/server/index.cjs
grep -R "getServerPort" -n dist/server/index.cjs
```

## Devvit upload

From `devvit/`:

```bash
npx devvit upload
```

Do not publish until the fetch domain is approved and the app details include appropriate Terms and Privacy Policy links.

## Devvit playtest

Run:

```bash
npx devvit playtest r/<TEST_SUBREDDIT>
```

Create a recipe post or comment, then reply exactly:

```text
!recipecard
```

Expected Devvit logs when the trigger is working:

```text
RecipeBot onCommentCreate handler entered
RecipeBot checking comment command
RecipeBot backend request
```

If the fetch domain is still pending, the backend request will fail with:

```text
HTTP request to domain: <PUBLIC_BACKEND_DOMAIN> is not allowed
```

That means the adapter is working, but Reddit has not approved the external fetch domain yet.

## Legacy Reddit command listener

The PRAW listener is retained only as an optional legacy adapter. It is not the preferred Reddit integration path.

Use Devvit for normal RecipeBot command ingestion.

The PRAW path is useful only if you intentionally want to run an external Reddit bot account with traditional Reddit API credentials. Unlike Devvit, the PRAW path can perform private-message result delivery and optional public fallback replies, but that behavior does not apply to the Devvit adapter.

The PRAW listener recognizes only a standalone `!recipecard` comment. Extra text, flags, partial words, deleted comments, and comments authored by the configured bot account are ignored. Ingestion records the requesting username so the worker can privately deliver completed results.

Set the listener configuration in `.env`:

```bash
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

`ENABLED_SUBREDDITS` is the complete allowlist. The listener combines only those names into the PRAW comment stream.

Start it locally after Postgres is running and migrations are applied:

```bash
python -m scripts.run_reddit_listener
```

`REDDIT_DRY_RUN=true` keeps all Reddit-side writes disabled while still allowing source, recipe, queued-job, artifact, and queued-message database records.

Completed PRAW jobs normally send the requester a private message containing the card landing page plus direct PNG, PDF, SVG, and ZIP links. Delivery attempts are stored in the `messages` table.

A DM failure leaves the artifacts intact and fails the job unless:

```bash
REDDIT_PUBLIC_FALLBACK_ON_DM_FAILURE=true
```

With that explicit opt-in, RecipeBot replies to the original command with only the landing-page URL. The fallback is off by default.

This optional acknowledgement posts a short reply when a new command is queued:

```bash
REDDIT_PUBLIC_ACK_ON_QUEUE=true
```

It is also off by default.

Neither delivery option changes command parsing or accepts per-command flags.

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

The web container listens on port `8000` internally and is published only at:

```text
127.0.0.1:8097
```

Postgres remains internal at:

```text
postgres:5432
```

and is published for host tools only at:

```text
127.0.0.1:${POSTGRES_HOST_PORT:-55432}
```

Worker and web containers share the host `./artifacts` directory.

To create a demo job against the Compose database, run:

```bash
docker compose run --rm worker python -m scripts.create_sample_job
```

Open the card page after the worker completes it:

```text
http://127.0.0.1:8097/cards/<card-id>
```

The legacy PRAW listener is behind an explicit Compose profile and remains off during normal `docker compose up`.

With the Reddit variables in `.env`, start it using:

```bash
docker compose --profile reddit up bot
```

## Production deployment

Production deployment uses `docker-compose.prod.yml`.

The production stack includes:

- isolated Postgres container
- migration service
- Flask/Gunicorn web service
- worker service
- optional profiled legacy bot service

Application containers connect through:

```text
postgres:5432
```

Host access to Postgres is loopback-only by default.

The production web service should be bound to a loopback host port and exposed publicly only through a reverse proxy.

The application image installs:

- ImageMagick
- deterministic fonts
- `librsvg2-bin`

SVG rasterization calls `rsvg-convert` directly. ImageMagick remains responsible for PDF generation.

## Production startup

On the deployment host:

```bash
git pull

sudo docker compose -f docker-compose.prod.yml up -d postgres
sudo docker compose -f docker-compose.prod.yml run --rm migrate
sudo docker compose -f docker-compose.prod.yml up -d web worker
```

Verify:

```bash
sudo docker compose -f docker-compose.prod.yml ps
curl -I https://<PUBLIC_BACKEND_DOMAIN>/health
curl -I https://<PUBLIC_BACKEND_DOMAIN>/terms
curl -I https://<PUBLIC_BACKEND_DOMAIN>/privacy
```

Watch backend logs:

```bash
sudo docker compose -f docker-compose.prod.yml logs -f web worker
```

Once the Devvit fetch domain is approved, a successful command should produce this flow:

```text
Devvit trigger
  -> signed POST to Flask
  -> backend queues job
  -> worker renders artifacts
  -> card page appears under /cards/<id>
```

## Reverse proxy

Configure your reverse proxy to terminate HTTPS and forward traffic to the Flask/Gunicorn web service.

Example route shape:

```text
Host: <PUBLIC_BACKEND_DOMAIN>
Target: http://127.0.0.1:8097
```

Set:

```bash
ARTIFACT_BASE_URL=https://<PUBLIC_BACKEND_DOMAIN>/cards
```

URLs written to `metadata.json` use the public hostname.

The reverse proxy is host-managed and is not started or modified by Compose.

## Useful commands

Devvit upload flow:

```bash
cd devvit

npm install
npm test
npm run typecheck
npm run build
npx devvit upload
```

Devvit playtest flow:

```bash
cd devvit
npx devvit playtest r/<TEST_SUBREDDIT>
```

Backend logs:

```bash
sudo docker compose -f docker-compose.prod.yml logs -f web worker
```

Artifact smoke test:

```bash
sudo docker compose -f docker-compose.prod.yml run --rm worker python -m scripts.create_sample_job
sudo docker compose -f docker-compose.prod.yml run --rm worker python -m scripts.run_worker_once

find artifacts/jobs -maxdepth 2 -type f | sort | tail -30
```

Public endpoint checks:

```bash
curl -I https://<PUBLIC_BACKEND_DOMAIN>/health
curl -I https://<PUBLIC_BACKEND_DOMAIN>/terms
curl -I https://<PUBLIC_BACKEND_DOMAIN>/privacy
```

## Troubleshooting

### Devvit fetch domain is not approved

The Devvit adapter cannot call:

```text
https://<PUBLIC_BACKEND_DOMAIN>/internal/devvit/recipecard
```

until Reddit approves the domain exception for:

```text
<PUBLIC_BACKEND_DOMAIN>
```

While pending, playtest logs may show:

```text
HTTP request to domain: <PUBLIC_BACKEND_DOMAIN> is not allowed
```

That is not a Flask, Docker, DNS, TLS, HMAC, or command parsing failure.

### Devvit trigger runs but backend logs show nothing

If Devvit logs show:

```text
RecipeBot onCommentCreate handler entered
RecipeBot checking comment command
RecipeBot backend request
```

but the backend receives no request, check Devvit fetch-domain approval first.

If the domain is approved, check:

- `RECIPEBOT_BACKEND_URL`
- `RECIPEBOT_WEBHOOK_SECRET`
- backend `DEVVIT_WEBHOOK_SECRET`
- backend `DEVVIT_INGESTION_ENABLED`
- backend public HTTPS reachability
- reverse proxy routing
- backend logs

### Devvit playtest build script fails

If playtest shows an error like:

```text
cp: unrecognized option '--watch'
```

then the npm dev/watch script is passing `--watch` through to a command that does not accept it.

Separate build and watch behavior so only `esbuild` receives watch mode, or use a small Node copy script that runs after build.

## What RecipeBot does not do

The preferred Devvit adapter does not:

- render recipe cards inside Devvit
- store recipes inside Devvit
- write to Postgres directly
- send DMs
- post public replies
- upload Reddit media
- use Redis
- use PRAW
- use Reddit username/password auth
- use Reddit OAuth client ID/client secret auth

Those responsibilities either do not exist yet, belong to the Flask backend, or belong only to the optional legacy PRAW adapter.
