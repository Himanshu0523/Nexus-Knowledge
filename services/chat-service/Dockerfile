FROM python:3.9-slim

WORKDIR /app

# Handle build context from root or subdirectory
COPY services/chat-service/requirements.txt* requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; elif [ -f services/chat-service/requirements.txt ]; then pip install --no-cache-dir -r services/chat-service/requirements.txt; fi

COPY services/chat-service/src/ ./src/
COPY services/chat-service/src/* ./src/ 2>/dev/null || true
COPY src/ ./src/ 2>/dev/null || true

WORKDIR /app/src

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
