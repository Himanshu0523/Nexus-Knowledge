FROM python:3.9-slim

WORKDIR /app

# Set Python path so imports like 'from config import settings' and 'from src.config import settings' both work
ENV PYTHONPATH="/app:/app/src"

# Copy requirements and install
COPY requirements.txt* api-gateway/requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; elif [ -f api-gateway/requirements.txt ]; then pip install --no-cache-dir -r api-gateway/requirements.txt; fi

# Copy service source code
COPY api-gateway/src/ ./src/

# Fallback copy if built from inside api-gateway directory directly
COPY src/ ./src/ 2>/dev/null || true

CMD ["sh", "-c", "if [ -f 'src/main.py' ]; then uvicorn src.main:app --host 0.0.0.0 --port 8000; elif [ -f 'main.py' ]; then uvicorn main:app --host 0.0.0.0 --port 8000; else cd src && uvicorn main:app --host 0.0.0.0 --port 8000; fi"]