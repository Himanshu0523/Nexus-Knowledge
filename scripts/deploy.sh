#!/bin/bash

set -e

ENVIRONMENT=${1:-production}
REGISTRY=${REGISTRY:-localhost:5000}
VERSION=${VERSION:-$(git rev-parse --short HEAD 2>/dev/null || echo "latest")}

echo "Deploying chatbot platform..."
echo "Environment: $ENVIRONMENT"
echo "Version: $VERSION"

echo "Building Docker images..."
docker build -t $REGISTRY/api-gateway:$VERSION api-gateway/
docker build -t $REGISTRY/chat-service:$VERSION services/chat-service/
docker build -t $REGISTRY/audit-service:$VERSION -f services/audit-service/Dockerfile .
docker build -t $REGISTRY/analytics-service:$VERSION -f services/analytics-service/Dockerfile .
docker build -t $REGISTRY/moderation-service:$VERSION -f services/moderation-service/Dockerfile .

if [ "$ENVIRONMENT" = "kubernetes" ]; then
    echo "Deploying to Kubernetes..."
    kubectl apply -f infra/k8s/namespace.yaml
    kubectl apply -f infra/k8s/
    
    kubectl set image deployment/api-gateway api-gateway=$REGISTRY/api-gateway:$VERSION -n chatbot-platform
    kubectl set image deployment/chat-service chat-service=$REGISTRY/chat-service:$VERSION -n chatbot-platform
    
    kubectl rollout status deployment/api-gateway -n chatbot-platform
    kubectl rollout status deployment/chat-service -n chatbot-platform
else
    echo "Deploying with Docker Compose..."
    VERSION=$VERSION docker-compose -f docker-compose.yml up -d
fi

echo "Deployment complete!"
