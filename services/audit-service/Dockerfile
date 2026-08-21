FROM python:3.9-slim

WORKDIR /app

COPY services/audit-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY services/audit-service/ .

CMD ["python", "src/consumer.py"]
