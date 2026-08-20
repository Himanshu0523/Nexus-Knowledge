#!/usr/bin/env python3
"""Validate environment configuration"""

import os
import sys

REQUIRED_VARS = {
    "development": [
        "DATABASE_URL",
        "REDIS_URL",
        "JWT_SECRET",
        "LLM_PROVIDER",
    ],
    "production": [
        "DATABASE_URL",
        "REDIS_URL",
        "JWT_SECRET",
        "API_KEY_SALT",
        "LLM_PROVIDER",
        "KAFKA_BROKERS",
        "ALLOWED_ORIGINS",
    ]
}

def check_required_vars(env: str):
    missing = []
    required = REQUIRED_VARS.get(env, REQUIRED_VARS["development"])
    for var in required:
        if not os.getenv(var):
            missing.append(var)
    return missing

def main():
    env = os.getenv("APP_ENV", "development")
    print(f"Validating environment for: {env}")
    
    missing = check_required_vars(env)
    if missing:
        print("\n❌ Missing required variables:")
        for var in missing:
            print(f"  - {var}")
        sys.exit(1)
    
    print("\n✅ Environment validation passed")
    print(f"  Environment: {env}")
    print(f"  Database URL: {os.getenv('DATABASE_URL')}")

if __name__ == "__main__":
    main()
