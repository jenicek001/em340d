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

# Set up permissions for external user (em340:dialout = 1001:20)
# Don't create internal user - container will run as host user
RUN chmod 755 /app \
    && chmod 755 /app/logs \
    && chmod 644 /app/*.py

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check to ensure the application can start
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import minimalmodbus, yaml; print('Dependencies OK')" || exit 1

# Default command
CMD ["python", "em340.py"]
