FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r app && useradd -r -g app app && \
    mkdir -p /home/app && chown -R app:app /home/app

# Install deps
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy app
COPY backend /app/backend
COPY data /app/data

# Ensure ownership for non-root user
RUN mkdir -p /app/data/.cache && \
    chown -R app:app /app

EXPOSE 5000

ENV HOST=0.0.0.0 PORT=5000 \
    HOME=/home/app \
    HF_HOME=/app/data/.cache \
    HF_DATASETS_CACHE=/app/data/.cache/datasets \
    HUGGINGFACE_HUB_CACHE=/app/data/.cache/hub

# Switch to non-root user
USER app

CMD ["python", "-m", "backend.app"]
