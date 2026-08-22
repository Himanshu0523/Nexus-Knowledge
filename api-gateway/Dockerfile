FROM python:3.9-slim

WORKDIR /app

# Handle build context from root or subdirectory
COPY api-gateway/requirements.txt* requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; elif [ -f api-gateway/requirements.txt ]; then pip install --no-cache-dir -r api-gateway/requirements.txt; fi

COPY api-gateway/src/ ./src/
COPY api-gateway/src/* ./src/ 2>/dev/null || true
COPY src/ ./src/ 2>/dev/null || true

WORKDIR /app/src

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]