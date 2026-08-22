FROM python:3.9-slim

WORKDIR /app

# Copy requirements from root or subfolder
COPY requirements.txt* api-gateway/requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; elif [ -f api-gateway/requirements.txt ]; then pip install --no-cache-dir -r api-gateway/requirements.txt; fi

# Copy source files
COPY api-gateway/src/ ./src/
COPY api-gateway/src/ ./app_src/
WORKDIR /app

# Ensure entrypoint finds main.py regardless of build context
CMD ["sh", "-c", "if [ -d 'src' ]; then uvicorn src.main:app --host 0.0.0.0 --port 8000; else uvicorn main:app --host 0.0.0.0 --port 8000; fi"]