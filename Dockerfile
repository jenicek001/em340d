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

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create logs directory
RUN mkdir -p /app/logs

# Copy application code
COPY *.py ./

# Create matching user and group for host em340 user (1001:20)
# This ensures proper file permissions for volumes
RUN groupadd -g 20 dialout_container 2>/dev/null || true \
    && groupadd -g 1001 em340_container 2>/dev/null || true \
    && useradd -u 1001 -g 1001 -G 20 -d /app -s /bin/bash em340_container \
    && chown -R em340_container:em340_container /app \
    && chmod 755 /app \
    && chmod 755 /app/logs \
    && chmod 644 /app/*.py

# Switch to the em340 user
USER em340_container

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check to ensure the application can start
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import minimalmodbus, yaml; print('Dependencies OK')" || exit 1

# Default command
CMD ["python", "em340.py"]
