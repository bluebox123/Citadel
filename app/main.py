"""
GuardRail-AI — FastAPI application entry point.

Middleware stack (outermost → innermost, i.e. request processing order):
  CORSMiddleware  →  FirewallMiddleware  →  ServerErrorMiddleware  →  ExceptionMiddleware  →  Router

Starlette builds the stack by iterating user_middleware in reverse, so the
last-registered middleware is outermost and sees every request first.
CORSMiddleware is outermost so it can attach CORS headers to all responses,
including 400 rejections emitted directly by FirewallMiddleware.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import proxy as proxy_v1
from app.middleware.firewall import FirewallMiddleware
from app.ml.classifier import load_model as load_ml_model
from app.parser.engine import validate_parser_at_startup
from app.utils.crypto import validate_key_at_startup
from app.utils.logging_config import configure_logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown hooks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    # Both checks enforce fail-fast: misconfiguration surfaces at boot, not
    # on the first live request.
    validate_key_at_startup()       # HMAC key present and ≥ 32 bytes
    validate_parser_at_startup()    # CFG grammar compiled without error
    load_ml_model()                 # ML classifier (graceful if model.pkl absent)
    logger.info("GuardRail-AI starting up")
    yield
    logger.info("GuardRail-AI shutting down")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GuardRail-AI",
    description=(
        "Cryptographically secured LLM firewall and grammar-strict proxy. "
        "All inbound prompts are scanned for injection attacks before "
        "being signed and forwarded to the target LLM API."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)

# FirewallMiddleware is registered first (becomes inner) so that CORSMiddleware
# (registered last, becomes outermost) can wrap Firewall responses and attach
# CORS headers even to 400 rejection payloads — otherwise the browser gets a
# CORS error instead of the readable 400 body.
app.add_middleware(FirewallMiddleware)

# CORS — allow both the default and fallback Next.js dev ports, plus any
# production origin set via the ALLOWED_ORIGINS environment variable.
# Must be registered AFTER FirewallMiddleware so it is outermost and wraps all
# responses (including Firewall rejections) with Access-Control-Allow-* headers.
_allowed_origins: list[str] = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
] or [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["X-Guardrail-Signature"],
)

# v1 routes — gateway pipeline lives in proxy_v1.router.
app.include_router(proxy_v1.router)


# ---------------------------------------------------------------------------
# Ops endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    tags=["ops"],
    summary="Liveness probe",
    response_description="Service is alive",
)
async def health() -> dict[str, str]:
    """
    Liveness probe.  Must respond in <10 ms with no external dependencies.
    Used by Docker HEALTHCHECK, Kubernetes liveness probe, and load balancers.
    """
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Dev-mode entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
        log_level="info",
    )
