FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    YTPI_HOST=0.0.0.0 \
    YTPI_PORT=7434 \
    YTPI_DB_PATH=/app/data/jobs.db \
    YTPI_DOWNLOADS_DIR=/app/downloads

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg gosu ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=denoland/deno:bin-2.9.4 /deno /usr/local/bin/deno
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 10001 appuser
COPY . .
RUN mkdir -p /app/data /app/downloads && chown -R appuser:appuser /app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh
EXPOSE 7434
VOLUME ["/app/data", "/app/downloads"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7434/healthz', timeout=3).read()"
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["waitress-serve", "--listen=0.0.0.0:7434", "app:app"]
