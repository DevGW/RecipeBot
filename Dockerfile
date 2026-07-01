FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        fonts-dejavu-core \
        fonts-liberation \
        imagemagick \
        libpq5 \
        librsvg2-bin \
    && sed -i 's/rights="none" pattern="PDF"/rights="write" pattern="PDF"/' \
        /etc/ImageMagick-6/policy.xml \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && useradd --create-home --uid 10001 recipebot \
    && mkdir -p /app/artifacts \
    && chown -R recipebot:recipebot /app

USER recipebot
EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app.web.server:create_app()"]
