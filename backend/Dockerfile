# ===========================================================================
# Samaritan Backend Dockerfile
# ===========================================================================
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Install python dependencies as wheels
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# ---------------------------------------------------------------------------
FROM python:3.13-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r samaritan && useradd -r -g samaritan samaritan

# Copy and install wheels
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy application source
COPY . .

# Set proper ownership
RUN chown -R samaritan:samaritan /app

USER samaritan

# Expose API port
EXPOSE 8000

# Start Uvicorn Server by default
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
