# RecipeBot

RecipeBot is a Python foundation for turning recipes into portable SVG, PNG, and PDF cards. This stage includes configuration, Postgres models, Alembic migrations, and local ImageMagick rendering. It intentionally does not connect to Reddit or include a task queue or web API.

## Requirements

- Python 3.12+
- ImageMagick 7 (`magick` on your `PATH`)
- Docker, if you want to run the local Postgres service

## Setup

Create a virtual environment and install the project with its development tools:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Start Postgres and apply the initial migration when database access is needed:

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

The first command prints the new job id. The worker claims that job with Postgres row locking and writes its artifacts to `artifacts/jobs/<job-id>/card.svg`, `card.png`, and `card.pdf`.

To run the single-process worker continuously instead, use:

```bash
python -m app.jobs.worker
```

The messaging lifecycle state is reserved for a later integration. No Reddit API behavior is present.
