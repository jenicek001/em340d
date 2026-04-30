# Dockerfile for EM340D - Single stage for simplicity on Raspberry Pi
FROM python:3.12-slim

LABEL maintainer="EM340D Project"
LABEL description="Carlo Gavazzi EM340 ModBus to MQTT Gateway"

WORKDIR /app

# Install system dependencies for serial communication
RUN apt-get update && apt-get install -y --no-install-recommends \
    udev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Poetry and project dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi \
    && pip uninstall -y poetry

# Create logs directory
RUN mkdir -p /app/logs

# Copy application source and static sensor configuration
COPY src/ ./src/
COPY config/sensors.yaml ./config/sensors.yaml

# Create matching user and group for host user permissions
ARG USER_ID=1000
ARG GROUP_ID=1000
ARG DIALOUT_GID=20

RUN groupadd -g ${DIALOUT_GID} dialout_container 2>/dev/null || true \
    && groupadd -g ${GROUP_ID} em340_container 2>/dev/null || true \
    && useradd -u ${USER_ID} -g ${GROUP_ID} -G ${DIALOUT_GID} -d /app -s /bin/bash em340_container \
    && chown -R em340_container:em340_container /app \
    && chmod 755 /app \
    && chmod 755 /app/logs \
    && chmod -R 644 /app/src/*.py \
    && chmod 644 /app/config/sensors.yaml

# Switch to the em340 user
USER em340_container

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src

# Health check to ensure the application can start
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import minimalmodbus, yaml; print('Dependencies OK')" || exit 1

# Default command
CMD ["python", "src/em340.py"]
