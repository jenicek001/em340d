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

# Create non-root user for security and fix permissions
RUN groupadd -r em340 && useradd -r -g em340 -d /app em340 \
    && chown -R em340:em340 /app

# Switch to non-root user
USER em340

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check to ensure the application can start
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import minimalmodbus, yaml; print('Dependencies OK')" || exit 1

# Default command
CMD ["python", "em340.py"]
