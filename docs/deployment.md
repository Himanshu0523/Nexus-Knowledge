# Phase 10: Production Architecture & Deployment Guide

## 1. Local Production Stack (`docker-compose`)

To launch the full production topology locally:

```bash
docker-compose up -d --build
```

This starts:
- **API Gateway** (`:8000`)
- **Chat Service** (`:8001`)
- **Audit Service** (Kafka Consumer)
- **Analytics Service** (Kafka Consumer)
- **Moderation Service** (Kafka Consumer)
- **PostgreSQL 14** (`:5432`)
- **Redis 7** (`:6379`)
- **Qdrant Vector DB** (`:6333`)
- **Confluent Kafka & Zookeeper** (`:9092`)

---

## 2. Kubernetes Deployment (`kubectl`)

Manifests are located in `infra/k8s/`:

```bash
# 1. Create Namespace
kubectl apply -f infra/k8s/namespace.yaml

# 2. Deploy Services
kubectl apply -f infra/k8s/api-gateway.yaml
kubectl apply -f infra/k8s/chat-service.yaml

# 3. Enable Horizontal Pod Autoscaler (HPA)
kubectl apply -f infra/k8s/autoscaling.yaml

# 4. Apply Ingress Controller Rule
kubectl apply -f infra/k8s/ingress.yaml
```

---

## 3. Observability Setup

- **Prometheus Scrape Config:** Located at `infra/monitoring/prometheus.yml`.
- **Health Endpoints:**
  - Liveness: `GET /health/live`
  - Readiness: `GET /health/ready`
  - Overall status: `GET /health`

---

## 4. Continuous Integration (CI/CD)

The GitHub Actions pipeline `.github/workflows/ci.yml` runs on every push:
1. Spins up test databases (PostgreSQL & Redis).
2. Executes security test suite (`test_security.py`).
3. Builds containerized Docker images tagged with git SHA.
