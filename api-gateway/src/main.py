from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid

try:
    from config import settings
except ImportError:
    from src.config import settings

from routes.chat import router as chat_router
from routes.chat_stream import router as chat_stream_router
from routes.documents import router as documents_router
from routes.tools import router as tools_router
from middleware.auth import verify_api_key
from middleware.rate_limit import rate_limit_middleware
from middleware.logging import logging_middleware
from middleware.security_headers import SecurityHeadersMiddleware
from shared.security.idempotency import IdempotencyManager, IdempotencyMiddleware
from shared.telemetry import TelemetryMiddleware, register_telemetry_routes, setup_telemetry_logging

setup_telemetry_logging("api-gateway")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Automated Telemetry middleware (Tracing, Context, Prometheus metrics)
app.add_middleware(TelemetryMiddleware, service_name="api-gateway")

# Idempotency middleware
idempotency_manager = IdempotencyManager()
app.add_middleware(IdempotencyMiddleware, manager=idempotency_manager)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware
allowed_origins = [origin.strip() for origin in getattr(settings, "ALLOWED_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True if allowed_origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Request-ID"] = request_id
    
    return response

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "request_id": getattr(request.state, "request_id", None)
            }
        }
    )

# Include routers
app.include_router(chat_router, prefix=settings.API_PREFIX)
app.include_router(chat_stream_router, prefix=settings.API_PREFIX)
app.include_router(documents_router, prefix=settings.API_PREFIX)
app.include_router(tools_router, prefix=settings.API_PREFIX)

register_telemetry_routes(app)

@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "healthy",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/health/live")
@app.get("/healthz")
async def liveness_check():
    return {"status": "alive"}

@app.get("/health/ready")
@app.get("/readyz")
async def readiness_check():
    # Verify gateway dependencies if any
    return {"status": "ready"}
