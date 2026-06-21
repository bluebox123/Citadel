"""
Inbound firewall ASGI middleware.

Design rationale:
- Pure ASGI (no BaseHTTPMiddleware): eliminates Starlette's async-generator
  double-wrapping cost (~0.2 ms per request on CPython 3.11).
- Body is read once, decoded once, lowercased once; all signature checks run
  on that single string so we pay O(n) decode overhead only once per request.
- Literal-string `in` tests use CPython's C-level two-way string search —
  faster than compiled regex for fixed, non-anchored patterns.
- Signatures ordered by observed attack prevalence; `any()`-equivalent loop
  exits on the first match (hot path: clean request does a full scan, flagged
  request exits early).
- Pre-built rejection bytes + headers are module-level constants so the 400
  path is zero-allocation at call time.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.ml.classifier import classify

logger = logging.getLogger(__name__)


def _extract_text(body_text: str) -> str:
    """
    Extract all string values from a JSON body to form the ML input.
    Falls back to the raw body text if parsing fails.

    This ensures the ML classifier sees "how do I make a bomb" rather than
    '{"prompt": "how do I make a bomb"}' — JSON structure is not a signal.
    """
    try:
        parsed = json.loads(body_text)
    except (json.JSONDecodeError, ValueError):
        return body_text

    parts: list[str] = []

    def _collect(obj: object) -> None:
        if isinstance(obj, str):
            parts.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                _collect(v)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item)

    _collect(parsed)
    return " ".join(parts) if parts else body_text

# ---------------------------------------------------------------------------
# Threat-signature catalogue
# ---------------------------------------------------------------------------
# All entries are lowercase; the scanner lowercases input before searching.
# Grouped by attack category; within each group, most-common patterns first.
_SIGNATURES: tuple[str, ...] = (
    # -- Direct instruction overrides (highest prevalence) -------------------
    "ignore all previous instructions",
    "ignore previous instructions",
    "disregard all previous instructions",
    "disregard previous instructions",
    "forget all previous instructions",
    "forget previous instructions",
    "ignore the above instructions",
    "disregard the above",
    "ignore everything above",
    "ignore your instructions",
    "ignore your programming",
    "override your instructions",
    "new instructions:",
    "your new instructions",
    # -- Mode / privilege escalation -----------------------------------------
    "system override",
    "developer mode",
    "dan mode",
    "do anything now",
    "unrestricted mode",
    "jailbreak mode",
    "sudo mode",
    "admin mode",
    "god mode",
    "no restrictions",
    "act without restrictions",
    "act as if you have no restrictions",
    # -- Persona hijack -------------------------------------------------------
    "act as a developer mode",
    "act as if you are",
    "pretend you are",
    "pretend to be",
    "you are now",
    "from now on you are",
    "roleplay as",
    "role-play as",
    "simulate being",
    "you are not an ai",
    "you are not a language model",
    # -- Constraint removal ---------------------------------------------------
    "ignore ethics",
    "ignore morality",
    "ignore safety guidelines",
    "bypass your",
    "override your",
    # -- Injection markers (structural / XML-like) ----------------------------
    "[system]",
    "<system>",
    "###instruction",
    "<<sys>>",
    "prompt injection",
    "jailbreak",
)

# ---------------------------------------------------------------------------
# Pre-built 400 responses (zero allocation on the rejection paths)
# ---------------------------------------------------------------------------
_REJECT_PAYLOAD: bytes = json.dumps(
    {
        "error": "Security violation detected",
        "reason": "Prompt injection signature matched",
    },
    separators=(",", ":"),
).encode("utf-8")

_REJECT_HEADERS: list[list[bytes]] = [
    [b"content-type", b"application/json; charset=utf-8"],
    [b"content-length", str(len(_REJECT_PAYLOAD)).encode()],
    [b"x-citadel-decision", b"reject"],
]

_ML_REJECT_PAYLOAD: bytes = json.dumps(
    {
        "error": "Content policy violation",
        "reason": "Harmful content detected",
    },
    separators=(",", ":"),
).encode("utf-8")

_ML_REJECT_HEADERS: list[list[bytes]] = [
    [b"content-type", b"application/json; charset=utf-8"],
    [b"content-length", str(len(_ML_REJECT_PAYLOAD)).encode()],
    [b"x-citadel-decision", b"reject-ml"],
]

# ---------------------------------------------------------------------------
# Target scope
# ---------------------------------------------------------------------------
_GUARDED_PATH: str = "/api/v1/gateway"
_POST: str = "POST"


# ---------------------------------------------------------------------------
# Scan — hot path
# ---------------------------------------------------------------------------

def _contains_threat(body_lower: str) -> str | None:
    """
    Return the matched signature string if a threat is found, else None.

    Uses an explicit loop (not `any()` + generator) to avoid per-iteration
    generator frame overhead on CPython when the common result is False.
    """
    for sig in _SIGNATURES:
        if sig in body_lower:
            return sig
    return None


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

_ASGIApp = Callable[[dict[str, Any], Callable, Callable], Awaitable[None]]


class FirewallMiddleware:
    """
    Pure-ASGI inbound firewall for POST /api/v1/gateway.

    Request lifecycle:
      1. Non-target requests pass through with zero overhead.
      2. Target requests: body buffered → decoded → lowercased → scanned.
      3. Threat detected  → HTTP 400 emitted; downstream never called.
      4. Clean request    → body replayed via synthetic receive(); downstream
         sees an unmodified request with full body available.
    """

    __slots__ = ("app",)

    def __init__(self, app: _ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        # ── Fast-path: skip non-HTTP traffic (WebSocket, lifespan, etc.) ──
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # ── Fast-path: skip non-POST or non-guarded paths ─────────────────
        if scope["method"] != _POST or scope["path"] != _GUARDED_PATH:
            await self.app(scope, receive, send)
            return

        # ── Body ingestion ─────────────────────────────────────────────────
        # Optimistic single-chunk read (covers ~99 % of real-world requests).
        # Falls back to accumulation loop only when more_body is True.
        message = await receive()
        raw_body: bytes = message.get("body", b"")

        if message.get("more_body", False):
            chunks: list[bytes] = [raw_body]
            while True:
                message = await receive()
                chunk = message.get("body", b"")
                if chunk:
                    chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            raw_body = b"".join(chunks)

        # ── Threat scan — Layer 1: rule-based ─────────────────────────────
        # Decode with `errors="replace"`: malformed UTF-8 cannot match our
        # ASCII-only signatures, so replacement chars are not a bypass vector.
        body_text = raw_body.decode("utf-8", errors="replace")
        body_lower = body_text.lower()
        matched = _contains_threat(body_lower)

        if matched:
            logger.warning(
                "Firewall [rules] rejected | path=%s sig=%r",
                scope["path"],
                matched,
            )
            await _emit_rejection(send)
            return

        # ── Threat scan — Layer 2: ML classifier ──────────────────────────
        # Runs only when model is loaded; gracefully skipped otherwise.
        # Extract plain string values from JSON so the model sees the actual
        # content, not JSON syntax tokens.
        ml = classify(_extract_text(body_text))
        if ml is not None and ml.is_harmful:
            logger.warning(
                "Firewall [ML] rejected | path=%s confidence=%.3f",
                scope["path"],
                ml.confidence,
            )
            await _emit_ml_rejection(send)
            return

        # ── Replay body for downstream ─────────────────────────────────────
        # Downstream handlers (e.g., FastAPI's Request.body()) call receive()
        # expecting to get the body.  We provide a synthetic callable that
        # returns the already-buffered bytes exactly once, then signals EOF.
        _replayed = False

        async def _replay() -> dict[str, Any]:
            nonlocal _replayed
            if not _replayed:
                _replayed = True
                return {"type": "http.request", "body": raw_body, "more_body": False}
            # Subsequent calls signal an empty, closed body (should not occur
            # in normal HTTP/1.1 or HTTP/2 request handling).
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, _replay, send)


# ---------------------------------------------------------------------------
# Rejection emitter
# ---------------------------------------------------------------------------

async def _emit_rejection(
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Write a pre-built HTTP 400 response (rule-based) and close the exchange."""
    await send(
        {
            "type": "http.response.start",
            "status": 400,
            "headers": _REJECT_HEADERS,
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": _REJECT_PAYLOAD,
            "more_body": False,
        }
    )


async def _emit_ml_rejection(
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Write a pre-built HTTP 400 response (ML-detected) and close the exchange."""
    await send(
        {
            "type": "http.response.start",
            "status": 400,
            "headers": _ML_REJECT_HEADERS,
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": _ML_REJECT_PAYLOAD,
            "more_body": False,
        }
    )
