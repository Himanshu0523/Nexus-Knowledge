FROM python:3.9-slim

WORKDIR /app

# Set Python path so imports like 'from config import settings' and 'from src.config import settings' both work
ENV PYTHONPATH="/app:/app/src"

# Copy requirements and install
COPY api-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules and service source code
COPY shared/ ./shared/
COPY api-gateway/src/ ./src/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]