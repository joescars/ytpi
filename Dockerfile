FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies (ffmpeg required by yt-dlp for metadata/thumbnails)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user (optional but recommended)
RUN useradd -m appuser
RUN mkdir -p /app/downloads && mkdir -p /app/downloads/Music-Videos && mkdir -p /app/downloads/YouTube
RUN chown -R appuser:appuser /app

# Copy application source
COPY . .

USER appuser

# Expose the Flask port
EXPOSE 7434

# Persist downloaded videos (bind or named volume recommended)
VOLUME ["/app/downloads"]
VOLUME ["/app/downloads/Music-Videos"]
VOLUME ["/app/downloads/YouTube"]

# Run the existing script directly (no code modifications)
CMD ["python", "app.py"]
