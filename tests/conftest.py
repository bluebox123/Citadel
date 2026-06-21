"""
Shared pytest configuration and fixtures for GuardRail-AI.

CRITICAL ORDER-OF-OPERATIONS:
  app/utils/crypto.py calls _load_key() at module-import time (eagerly, once).
  GUARDRAIL_SECRET_KEY must therefore exist in os.environ BEFORE any app
  module is imported — including indirect imports triggered by pytest's
  collection phase.

  Setting the variable at conftest.py module level (not inside a fixture)
  guarantees it is present when pytest first imports the test files and
  transitively imports the app package.
"""

from __future__ import annotations

import os
import secrets

# --- Set key before any app import -------------------------------------------
# token_hex(32) → 64 lowercase hex chars → 32 raw bytes (256-bit key).
# os.environ.setdefault leaves an already-present variable untouched, so a
# developer can export GUARDRAIL_SECRET_KEY in their shell and that value will
# be used instead of this generated one.
_TEST_HEX_KEY: str = secrets.token_hex(32)
os.environ.setdefault("GUARDRAIL_SECRET_KEY", _TEST_HEX_KEY)

# --- Now it is safe to import app modules ------------------------------------
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """
    Async HTTP client wired directly to the ASGI app via in-process transport.

    No network socket is opened; requests are dispatched inside the same
    Python process.  This gives full integration coverage (middleware stack,
    routing, response serialisation) at unit-test speed.
    """
    from app.main import app  # imported here so env var is already set above

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest.fixture(scope="session")
def secret_key() -> str:
    """
    The hex-encoded 32-byte secret key active for this test session.

    Tests that need to independently verify signatures (without going through
    the HTTP layer) can import crypto functions and call them directly — the
    same key will be loaded because it was set in the environment above.
    """
    return os.environ["GUARDRAIL_SECRET_KEY"]
