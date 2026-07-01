# Hemlock production deployment

Hemlock runs RecipeBot with `docker-compose.prod.yml`. The production stack owns its Postgres container and data volume; it does not use or modify Hemlock's existing host-level Postgres server.

RecipeBot Postgres listens inside Docker as `postgres:5432`. Compose publishes it only to `127.0.0.1:${POSTGRES_HOST_PORT:-55432}`, so an existing host Postgres on port `5432` does not conflict and the RecipeBot database is not publicly exposed.

## Production environment

From `/opt/recipebot`, copy `.env.example` to `.env`, restrict its permissions, and replace `CHANGE_ME_STRONG` in both `POSTGRES_PASSWORD` and `DATABASE_URL` with the same strong URL-safe password:

```env
POSTGRES_HOST_PORT=55432
POSTGRES_PASSWORD=CHANGE_ME_STRONG
DATABASE_URL=postgresql+psycopg://recipebot:CHANGE_ME_STRONG@postgres:5432/recipebot
ARTIFACT_ROOT=/app/artifacts
ARTIFACT_BASE_URL=https://recipebot.devgw.com/cards
WEB_HOST=0.0.0.0
WEB_PORT=8000
RSVG_CONVERT_BINARY=rsvg-convert
DEVVIT_INGESTION_ENABLED=true
DEVVIT_WEBHOOK_SECRET=CHANGE_ME_TO_A_LONG_RANDOM_SECRET
DEVVIT_REQUIRE_HMAC=true
DEVVIT_SIGNATURE_TOLERANCE_SECONDS=300
REDDIT_DRY_RUN=true
```

If the password contains URL-reserved characters, percent-encode it only in `DATABASE_URL`. Gunicorn binds the Flask application to `0.0.0.0:8000` inside its container; Compose still publishes the service only as `127.0.0.1:8097:8000` on Hemlock.

Prepare the bind-mounted artifact directory for the non-root application user:

```bash
sudo mkdir -p artifacts/jobs
sudo chown -R 10001:10001 artifacts
sudo chmod -R u+rwX artifacts
```

## Deploy or update

Use these commands exactly from the repository checkout:

```bash
cd /opt/recipebot
git pull
sudo docker compose -f docker-compose.prod.yml build
sudo docker compose -f docker-compose.prod.yml up -d postgres
sudo docker compose -f docker-compose.prod.yml run --rm migrate
sudo docker compose -f docker-compose.prod.yml up -d web worker
sudo docker compose -f docker-compose.prod.yml ps
curl -I http://127.0.0.1:8097/health
curl -I https://recipebot.devgw.com/health
```

After Dockerfile dependency changes, including the librsvg addition, force a clean rebuild of both runtime images:

```bash
sudo docker compose -f docker-compose.prod.yml build --no-cache worker web
```

Confirm the SVG rasterizer is installed before processing jobs:

```bash
sudo docker compose -f docker-compose.prod.yml run --rm worker rsvg-convert --version
```

The shared Docker image includes ImageMagick for PNG→PDF conversion, `librsvg2-bin` for direct SVG→PNG conversion, and the fonts used by the card layout.

## Devvit webhook

The Devvit app is the preferred Reddit adapter. It calls `POST https://recipebot.devgw.com/internal/devvit/recipecard` after detecting `!recipecard`. Nginx proxies this route to the same loopback-only Flask/Gunicorn service; no additional public container port is required.

Each request must include:

```text
X-RecipeBot-Timestamp: <Unix timestamp in seconds>
X-RecipeBot-Signature: <lowercase hex HMAC SHA-256>
```

Compute the signature over the exact raw HTTP body using the message `<timestamp>.<raw_request_body>` and `DEVVIT_WEBHOOK_SECRET` as the key. RecipeBot rejects missing or invalid signatures and timestamps more than `DEVVIT_SIGNATURE_TOLERANCE_SECONDS` away from the server clock. Keep `DEVVIT_REQUIRE_HMAC=true`, synchronize the host clock, and configure the same strong secret in the Devvit app without committing or logging it.

The endpoint is disabled by default. Set `DEVVIT_INGESTION_ENABLED=true` only after the secret is in place, then rebuild/restart `web`. Duplicate command comment ids safely return their existing Postgres job. The PRAW listener remains available only as an optional legacy profile.

Enable the optional Reddit listener only after its credentials and allowlist are configured:

```bash
sudo docker compose -f docker-compose.prod.yml --profile reddit up -d bot
```

The bot, migration, worker, and web services all use the internal `postgres:5432` address and wait for the database health check. Host tools can connect through `127.0.0.1:55432` by default.

## Existing Nginx vhost

Nginx remains host-managed and is not part of either Compose file. The `recipebot.devgw.com` location must proxy to the loopback-only web port:

```nginx
location / {
    proxy_pass http://127.0.0.1:8097;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Do not change the production port mappings to `0.0.0.0`; Nginx is the public entry point.

## Advanced external Postgres option

Operators who intentionally want an external database may override `DATABASE_URL` and remove or disable the Compose `postgres` service in their own advanced deployment overlay. That is not the default or supported Hemlock path; the repository-managed production deployment requires no host Postgres configuration changes.
