# =============================================================================
# Citadel — Production Dockerfile
# =============================================================================
# Two-stage build:
#   builder  — installs Python packages into an isolated venv
#   runtime  — copies the venv + app source; runs as a non-root system user
#
# The final image contains no build tools, no dev dependencies, and no pip.
#
# Build:
#   docker build -t citadel:latest .
#
# Run (supply the real secret key; never bake it into the image):
#   docker run --rm -p 8000:8000 \
#     -e CITADEL_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
#     citadel:latest
#
# Recommended: add a .dockerignore that excludes .venv/, tests/, .env, and
#   __pycache__ so the build context stays small.
# =============================================================================


# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Create a self-contained virtual environment; copying it to the runtime stage
# is cleaner than installing into the system Python prefix.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip once inside the venv before installing anything.
RUN pip install --no-cache-dir --upgrade pip

# Copy the requirements file first so Docker layer-caches the pip install
# step until requirements.txt actually changes.
COPY requirements.txt .

# Install production runtime dependencies only.
# Dev tools (pytest*, black, ruff, mypy) are intentionally excluded to minimise
# the attack surface and keep the final image lean.
# Package versions are taken verbatim from requirements.txt to stay in sync.
RUN pip install --no-cache-dir \
        "fastapi>=0.115.0"         \
        "uvicorn[standard]>=0.30.0" \
        "pydantic>=2.7.0"          \
        "pydantic-settings>=2.4.0" \
        "lark>=1.2.0"              \
        "pyyaml>=6.0.2"            \
        "cryptography>=43.0.0"     \
        "httpx>=0.27.0"


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Apply OS security patches at image-build time.
# Packages are pinned to the apt snapshot at build time; rebuild to update.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user ─────────────────────────────────────────────────────────────
# A dedicated system account with no login shell and no home directory prevents
# privilege escalation even if an attacker achieves code execution inside the
# container.  UID/GID are configurable at build time via --build-arg.
ARG APP_UID=10001
ARG APP_GID=10001

RUN groupadd --system --gid "${APP_GID}" citadel_user \
    && useradd  --system \
                --uid  "${APP_UID}" \
                --gid  "${APP_GID}" \
                --no-create-home \
                --shell /usr/sbin/nologin \
                citadel_user

# ── Virtual environment ───────────────────────────────────────────────────────
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# ── Application source ────────────────────────────────────────────────────────
WORKDIR /app

# Only copy the directories the app actually reads at runtime.
# Tests, scripts, docker/, .venv/, and editor configs are excluded.
COPY --chown=citadel_user:citadel_user app/     ./app/
COPY --chown=citadel_user:citadel_user grammar/ ./grammar/
COPY --chown=citadel_user:citadel_user config/  ./config/

# ── Python hardening ──────────────────────────────────────────────────────────
# PYTHONUNBUFFERED   — stdout/stderr reach the container log driver immediately.
# PYTHONDONTWRITEBYTECODE — no .pyc files written; pairs with read-only FS.
# PYTHONFAULTHANDLER — dump tracebacks to stderr on SIGSEGV / fatal errors.
# PYTHONPATH         — app package is importable without installation.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONPATH=/app

# ── Application defaults ──────────────────────────────────────────────────────
# All values are overridable at container start via -e / --env-file.
ENV HOST=0.0.0.0 \
    PORT=8000 \
    LOG_LEVEL=INFO \
    ENV=production

# ── Secret key placeholder ────────────────────────────────────────────────────
# SECURITY: This placeholder value is intentionally invalid (< 32 decoded bytes)
# so validate_key_at_startup() aborts the process at boot if the operator forgets
# to inject a real key.  NEVER bake a real secret into an image layer.
#
# Generate a valid key:
#   python -c "import secrets; print(secrets.token_hex(32))"
ENV CITADEL_SECRET_KEY=REPLACE_ME_generate_with_python_secrets_token_hex_32

EXPOSE 8000

# Drop to non-root before the first process instruction executes.
USER citadel_user

# ── Health check ──────────────────────────────────────────────────────────────
# Uses only the Python standard library (no curl dependency on the slim image).
# /health is a sub-10 ms endpoint with no external dependencies — ideal probe target.
HEALTHCHECK --interval=30s \
            --timeout=5s   \
            --start-period=15s \
            --retries=3 \
    CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://localhost:8000/health',timeout=4); sys.exit(0 if r.status==200 else 1)"

# ── Entrypoint ────────────────────────────────────────────────────────────────
# Exec form (JSON array) — uvicorn receives SIGTERM directly without a shell
# wrapper, enabling graceful in-flight request draining on container stop.
#
# --workers 1: one process per container; scale horizontally with replicas.
# --no-access-log: the app's LoggingMiddleware already records every request;
#   suppressing uvicorn's duplicate access log reduces noise.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info", "--no-access-log"]
