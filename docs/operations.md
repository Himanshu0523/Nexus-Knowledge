# Operations Guide

## Daily Operations

### Health Checks
```bash
./scripts/healthcheck.sh
```

### View Logs
```bash
# Docker Compose
docker-compose logs -f chat-service

# Kubernetes
kubectl logs -f deployment/chat-service -n chatbot-platform
```

### Scale Services
```bash
# Kubernetes
kubectl scale deployment chat-service --replicas=5 -n chatbot-platform
```

## Monitoring

### Key Metrics to Watch
- Request latency (P95, P99)
- Error rate
- LLM token usage
- Kafka consumer lag
- Database connection pool usage
- Cache hit rate

## Incident Response

### Service Down
1. Check health endpoints (`/health`, `/health/live`, `/health/ready`).
2. View container logs.
3. Check status of PostgreSQL, Redis, Qdrant, and Kafka.
4. Restart affected pods or containers.
