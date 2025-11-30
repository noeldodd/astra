# Dockerfile
# JARVIS WebSocket Backend

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port - this is just docs, not config!
EXPOSE 8008

# Run server
CMD ["sh", "-c", "uvicorn websocket_server:app --host 0.0.0.0 --port ${WEBSOCKET_PORT}"]