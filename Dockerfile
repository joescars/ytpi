FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    YTPI_HOST=0.0.0.0 \
    YTPI_PORT=7434 \
    YTPI_DOWNLOADS_DIR=/app/downloads \
    YTPI_DB_PATH=/app/data/jobs.db

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg gosu && \
    rm -rf /var/lib/apt/lists/*

# yt-dlp's --remote-components ejs:github (see YTPI_ENABLE_REMOTE_COMPONENTS) needs a JS
# runtime on PATH to execute the fetched component; deno is yt-dlp's default supported one.
COPY --from=denoland/deno:bin-2.1.4 /deno /usr/local/bin/deno

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

RUN useradd -m appuser

COPY . .

RUN mkdir -p /app/downloads /app/data && \
    chown -R appuser:appuser /app

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 7434

VOLUME ["/app/downloads", "/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7434/healthz', timeout=3).read()"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["waitress-serve", "--listen=0.0.0.0:7434", "app:app"]
