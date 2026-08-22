FROM python:3.9-slim

WORKDIR /app

# Set Python path so imports like 'from config import settings' and 'from src.config import settings' both work
ENV PYTHONPATH="/app:/app/src"

# Copy requirements and install
COPY requirements.txt* services/chat-service/requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; elif [ -f services/chat-service/requirements.txt ]; then pip install --no-cache-dir -r services/chat-service/requirements.txt; fi

# Copy source files
COPY services/chat-service/src/ ./src/

CMD ["sh", "-c", "if [ -f 'src/main.py' ]; then uvicorn src.main:app --host 0.0.0.0 --port 8001; elif [ -f 'main.py' ]; then uvicorn main:app --host 0.0.0.0 --port 8001; else cd src && uvicorn main:app --host 0.0.0.0 --port 8001; fi"]

