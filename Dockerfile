FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/ ./agent/

ENV UMS_MCP_URL=${UMS_MCP_URL} \
    DIAL_API_KEY=${DIAL_API_KEY} \
    ORCHESTRATION_MODEL=${ORCHESTRATION_MODEL} \
    DIAL_URL=${DIAL_URL} \
    REDIS_HOST=${REDIS_HOST} \
    REDIS_PORT=${REDIS_PORT}

EXPOSE 8000

CMD ["python", "agent/app.py"]