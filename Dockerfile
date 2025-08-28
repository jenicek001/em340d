# Multi-stage Dockerfile for EM340D
FROM python:3.12-slim as builder

# Build stage - install dependencies
WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.12-slim

LABEL maintainer="EM340D Project"
LABEL description="Carlo Gavazzi EM340 ModBus to MQTT Gateway"

WORKDIR /app

# Install system dependencies for serial communication
RUN apt-get update && apt-get install -y --no-install-recommends \
    udev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder stage
COPY --from=builder /root/.local /root/.local

# Create logs directory
RUN mkdir -p /app/logs

# Copy application code
COPY *.py ./

# Create non-root user for security
RUN groupadd -r em340 && useradd -r -g em340 -d /app em340
RUN chown -R em340:em340 /app

# Switch to non-root user
USER em340

# Environment variables
ENV PYTHONPATH=/root/.local/lib/python3.12/site-packages
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check to ensure the application can start
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import yaml, sys; exit(0 if 'em340.yaml' in sys.modules or yaml else 1)" || exit 1

# Default command
CMD ["python", "em340.py"]
