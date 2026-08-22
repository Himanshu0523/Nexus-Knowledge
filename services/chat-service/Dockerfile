FROM python:3.9-slim

WORKDIR /app

# Copy requirements from root or subfolder
COPY requirements.txt* services/chat-service/requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; elif [ -f services/chat-service/requirements.txt ]; then pip install --no-cache-dir -r services/chat-service/requirements.txt; fi

# Copy source files
COPY services/chat-service/src/ ./src/
WORKDIR /app

# Ensure entrypoint finds main.py regardless of build context
CMD ["sh", "-c", "if [ -d 'src' ]; then uvicorn src.main:app --host 0.0.0.0 --port 8001; else uvicorn main:app --host 0.0.0.0 --port 8001; fi"]
