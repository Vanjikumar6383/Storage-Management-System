"""
Main FastAPI Application Entrypoint.
Provides production middleware, correlation IDs, security headers, CORS policies, standardized error handling, and health endpoints.
"""

import time
import uuid
import logging
from typing import Callable
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_app_config, get_storage_settings, validate_aws_storage_config
from app.db.database import SessionLocal
from app.connectors.credentials import CredentialResolver

# Configure structured logging
app_config = get_app_config()
logging.basicConfig(
    level=getattr(logging, app_config.log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] [req_id=%(request_id)s] %(message)s",
)
logger = logging.getLogger("storage.main")


old_factory = logging.getLogRecordFactory()

def record_factory(*args, **kwargs):
    record = old_factory(*args, **kwargs)
    if not hasattr(record, "request_id"):
        record.request_id = "system"
    return record

logging.setLogRecordFactory(record_factory)

app = FastAPI(
    title=app_config.app_name,
    description="Production-oriented Multi-Tenant Storage Lifecycle Optimizer Control Plane",
    version="0.1.0",
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_and_security_headers_middleware(request: Request, call_next: Callable) -> Response:
    """
    Middleware generating X-Request-ID correlation headers, timing requests, and injecting HTTP security headers.
    """
    req_id = request.headers.get("X-Request-ID", f"req-{uuid.uuid4().hex[:12]}")
    request.state.request_id = req_id

    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        sanitized_err = CredentialResolver.sanitize_text(str(exc))
        logger.error(f"Unhandled exception on {request.method} {request.url.path} (duration: {duration_ms}ms): {sanitized_err}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected application error occurred.",
                    "request_id": req_id,
                }
            },
            headers={"X-Request-ID": req_id},
        )

    duration_ms = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    logger.info(f"{request.method} {request.url.path} - Status: {response.status_code} - {duration_ms}ms")
    return response


app.include_router(api_router, prefix="/api/v1")


@app.get("/health/liveness")
@app.get("/health")
def liveness_check():
    """Liveness check confirming application process is running."""
    return {"status": "HEALTHY", "service": app_config.app_name, "environment": app_config.app_env}


@app.get("/health/readiness")
def readiness_check():
    """
    Readiness check verifying database connectivity, configuration validity, and storage provider status.
    Secrets and credentials are NEVER exposed.
    """
    storage_opts = get_storage_settings()
    db_status = "HEALTHY"
    
    # Check PostgreSQL readiness
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        db_status = "DEGRADED"
        logger.error(f"Readiness check DB error: {CredentialResolver.sanitize_text(str(e))}")

    # Check Storage Provider readiness
    storage_status = "HEALTHY"
    missing_aws_keys = []
    if storage_opts.provider == "AWS_S3":
        is_valid, missing_aws_keys = validate_aws_storage_config(storage_opts)
        if not is_valid:
            storage_status = "DEGRADED"

    is_overall_ready = (db_status == "HEALTHY" and storage_status == "HEALTHY")
    status_code = status.HTTP_200_OK if is_overall_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "HEALTHY" if is_overall_ready else "DEGRADED",
            "application_status": "HEALTHY",
            "database_status": db_status,
            "storage_provider": storage_opts.provider,
            "storage_status": storage_status,
            "environment": app_config.app_env,
            "missing_aws_keys": missing_aws_keys if storage_opts.provider == "AWS_S3" else [],
        }
    )


@app.get("/info")
def system_info():
    """Basic service info endpoint."""
    storage_opts = get_storage_settings()
    return {
        "name": app_config.app_name,
        "version": "0.1.0",
        "environment": app_config.app_env,
        "storage_provider": storage_opts.provider,
        "delete_safety_mode": "SIMULATION_ONLY",
    }
