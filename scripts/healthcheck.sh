#!/bin/bash

API_GATEWAY_URL=${API_GATEWAY_URL:-http://localhost:8000}
CHAT_SERVICE_URL=${CHAT_SERVICE_URL:-http://localhost:8001}

check_service() {
    local url=$1
    local name=$2
    
    echo -n "Checking $name ($url)... "
    if curl -f -s "$url/health" > /dev/null 2>&1; then
        echo "OK"
        return 0
    else
        echo "FAILED"
        return 1
    fi
}

check_service $API_GATEWAY_URL "API Gateway"
check_service $CHAT_SERVICE_URL "Chat Service"
