FROM python:3.9-slim

WORKDIR /app

COPY services/analytics-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY services/analytics-service/ .

CMD ["python", "src/consumer.py"]
