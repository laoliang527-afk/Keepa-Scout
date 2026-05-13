# Build stage: install dependencies
# Using Daocloud mirror for China network compatibility
FROM docker.m.daocloud.io/library/python:3.11-slim AS deps

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runtime stage
FROM docker.m.daocloud.io/library/python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy installed packages from deps stage
COPY --from=deps /install /usr/local

# Copy only what Docker needs (data/ is mounted at runtime via volume)
COPY app/ ./app/
COPY data/ ./data/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# uvicorn is the main process (healthcheck depends on it)
# ETL runs in background — its failure is logged but does NOT crash the container
CMD ["/entrypoint.sh"]
