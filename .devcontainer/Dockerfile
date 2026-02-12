# Development container for ytpi project
FROM mcr.microsoft.com/devcontainers/python:3.11

# Avoid warnings by switching to noninteractive
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies including ffmpeg (required by yt-dlp)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    wget \
    vim \
    nano \
    htop \
    tree \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Switch back to dialog for any ad-hoc use of apt-get
ENV DEBIAN_FRONTEND=dialog

# Set the working directory
WORKDIR /workspace

# Create directories for downloads with proper permissions
RUN mkdir -p /workspace/downloads/shared \
    && mkdir -p /workspace/downloads/Music-Videos \
    && mkdir -p /workspace/downloads/YouTube \
    && chown -R vscode:vscode /workspace

# Install Python development tools
RUN pip install --upgrade pip \
    && pip install \
        pylint \
        autopep8 \
        black \
        flake8 \
        pytest \
        pytest-flask \
        python-dotenv

# Copy requirements and install project dependencies
COPY requirements.txt ./
RUN pip install -r requirements.txt \
    && pip install --upgrade yt-dlp

# Set environment variables for development
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=development \
    FLASK_DEBUG=1

# Expose the Flask development port
EXPOSE 7434

# Switch to vscode user
USER vscode

# Default command (can be overridden)
# CMD ["python", "app.py"]