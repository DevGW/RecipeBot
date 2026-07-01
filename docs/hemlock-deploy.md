# Hemlock production deployment

Hemlock runs RecipeBot's containers, Nginx, and the existing host-level Postgres server. Production uses `docker-compose.prod.yml`; that file deliberately has no `postgres` service and publishes only the web service on Hemlock's loopback interface.

## One-time Postgres setup

Connect to the host Postgres server as an administrator and create the application role and database:

```sql
CREATE USER recipebot WITH PASSWORD 'CHANGE_ME_STRONG';
CREATE DATABASE recipebot OWNER recipebot;
GRANT ALL PRIVILEGES ON DATABASE recipebot TO recipebot;
```

Replace the placeholder with a strong URL-safe password. If the password contains URL-reserved characters, percent-encode it in `DATABASE_URL`.

Postgres must listen on a host address reachable through Docker's host gateway, not only on its Unix socket or `127.0.0.1`. Set `listen_addresses` in `postgresql.conf` to the appropriate Hemlock bridge/gateway address (or another deliberately selected host address). Do not expose Postgres broadly to the internet.

If the current client rules do not cover the Docker network, add a narrowly scoped `pg_hba.conf` entry using Hemlock's actual Docker subnet. For example, after confirming the subnet rather than copying it blindly:

```conf
host    recipebot    recipebot    172.17.0.0/16    scram-sha-256
```

Inspect Docker's network configuration to find the correct subnet and restrict any host firewall rule to that subnet. Restart Postgres after changing `postgresql.conf` or `pg_hba.conf`:

```bash
sudo systemctl restart postgresql
```

## Production environment

From `/opt/recipebot`, copy `.env.example` to `.env`, restrict its permissions, and replace every placeholder. The required database connection uses Docker's host gateway name:

```env
DATABASE_URL=postgresql+psycopg://recipebot:CHANGE_ME@host.docker.internal:5432/recipebot
ARTIFACT_ROOT=/app/artifacts
ARTIFACT_BASE_URL=https://recipebot.devgw.com/cards
WEB_HOST=0.0.0.0
WEB_PORT=8000
REDDIT_DRY_RUN=true
```

`WEB_HOST=0.0.0.0` binds Uvicorn inside its container. Compose still publishes the service only as `127.0.0.1:8097:8000` on Hemlock.

## Deploy or update

Use these commands exactly from the repository checkout:

```bash
cd /opt/recipebot
git pull
sudo docker compose -f docker-compose.prod.yml build
sudo docker compose -f docker-compose.prod.yml run --rm migrate
sudo docker compose -f docker-compose.prod.yml up -d web worker
sudo docker compose -f docker-compose.prod.yml ps
curl -I http://127.0.0.1:8097/health
curl -I https://recipebot.devgw.com/health
```

Enable the optional Reddit listener only after its credentials and allowlist are configured:

```bash
sudo docker compose -f docker-compose.prod.yml --profile reddit up -d bot
```

The production Compose file never creates or publishes Postgres. `migrate`, `web`, `worker`, and `bot` each map `host.docker.internal` to Docker's host gateway and use the host database URL from `.env`.

## Existing Nginx vhost

Nginx remains host-managed and is not part of either Compose file. The `recipebot.devgw.com` location must proxy to the loopback-only container port:

```nginx
location / {
    proxy_pass http://127.0.0.1:8097;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Do not change the production port mapping to `0.0.0.0:8097`; Nginx is the public entry point.
