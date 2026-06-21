"""
Phase 2 gateway route — full request/response pipeline.

Request lifecycle (every POST /api/v1/gateway):
  FirewallMiddleware  [ASGI layer — runs before this module is reached]
    └─ POST /api/v1/gateway
         ├─ 1. Canonicalise JSON body + HMAC-SHA256 sign
         ├─ 2. Extract ``prompt`` field
         ├─ 3. mock_llm_call(prompt) → raw string
         ├─ 4. validate_llm_output(raw) — CFG grammar + json.loads()
         │      ├─ OutputParsingError → 502 Bad Gateway
         │      └─ success → validated tool-call dict
         └─ 5. 200 OK  {status, tool_call, signature_preview}
                header: X-GuardRail-Signature: <64-char hex>

Fail-closed status codes:
  400  Non-JSON body, or missing/invalid ``prompt`` field.
  502  LLM output failed CFG grammar validation.
  503  Secret key absent — crypto subsystem cannot operate.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.parser.engine import validate_llm_output
from app.parser.exceptions import OutputParsingError
from app.utils.crypto import canonicalize_payload, generate_hmac_signature

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Mock LLM ──────────────────────────────────────────────────────────────────

# Prompts containing this substring exercise the parser-rejection path.
_MALFORMED_TRIGGER: str = "edge_case"


async def mock_llm_call(prompt: str) -> str:
    """Simulate an LLM returning a structured tool-call JSON string.

    Deterministic routing rules (no I/O, no network):
      • ``edge_case`` in prompt → trailing-comma JSON (parser must reject).
      • ``fetch``    in prompt → fetch tool call.
      • ``compute``  in prompt → compute tool call.
      • anything else          → search tool call (default).

    In Phase 3 this is replaced by a real async HTTP call to the LLM API
    endpoint configured in LLM_API_BASE_URL, forwarding the signed payload
    and the X-GuardRail-Signature header.

    Args:
        prompt: Sanitised user prompt (firewall already passed it).

    Returns:
        Raw string exactly as an LLM would emit it — not yet validated.
    """
    prompt_lower = prompt.lower()

    if _MALFORMED_TRIGGER in prompt_lower:
        # Trailing comma in the arguments object — structurally invalid JSON.
        # The CFG parser will reject this before json.loads() is ever called.
        return '{"tool_name": "search", "arguments": {"query": "test",}}'

    if "fetch" in prompt_lower:
        return json.dumps({
            "tool_name": "fetch",
            "arguments": {"url": "https://example.com", "timeout": 30},
        })

    if "compute" in prompt_lower:
        return json.dumps({
            "tool_name": "compute",
            "arguments": {"expression": prompt[:80], "precision": 6},
        })

    # Default: search.
    return json.dumps({
        "tool_name": "search",
        "arguments": {"query": prompt[:120], "limit": 10},
    })


# ── Gateway endpoint ──────────────────────────────────────────────────────────

@router.post(
    "/api/v1/gateway",
    tags=["gateway"],
    summary="LLM proxy gateway",
    status_code=status.HTTP_200_OK,
)
async def gateway(request: Request) -> JSONResponse:
    """Secured LLM proxy — Phase 2 complete pipeline.

    Accepts a JSON body with a ``prompt`` field, signs it, calls the (mock)
    LLM, validates the output through the CFG grammar, and returns the
    validated tool-call dict.

    Expected request body::

        {
            "prompt": "search for recent AI papers",
            "context": {},
            "metadata": {}
        }

    Successful response (200)::

        {
            "status": "ok",
            "tool_call": {
                "tool_name": "search",
                "arguments": {"query": "search for recent AI papers", "limit": 10}
            },
            "signature_preview": "a1b2c3d4...ef01"
        }

    Parser-rejection response (502)::

        {
            "error": "LLM output structurally invalid",
            "details": "Syntax error at line 1, column 39"
        }
    """
    body: bytes = await request.body()

    # ── Step 1: Canonicalise & sign ───────────────────────────────────────────
    # Canonical form is key-order-independent (sorted keys, compact) so the
    # HMAC is identical regardless of client key-insertion order.
    try:
        canonical: str = canonicalize_payload(body)
    except ValueError as exc:
        logger.warning("Gateway rejected non-JSON body | reason=%s", exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Invalid request body",
                "reason": "Payload must be valid JSON",
            },
        )

    try:
        signature: str = generate_hmac_signature(canonical)
    except RuntimeError:
        logger.error(
            "Gateway signing failed: secret key not configured (fail-closed → 503)"
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Service unavailable"},
        )

    # ── Step 2: Extract prompt ────────────────────────────────────────────────
    # body already parsed by canonicalize_payload; re-use json.loads() here
    # (negligible cost — body is already in memory, typically < 10 KB).
    try:
        payload: dict[str, Any] = json.loads(body)
        prompt: str = payload["prompt"]
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
    except KeyError:
        logger.warning("Gateway request missing required field 'prompt'")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Invalid request body",
                "reason": "Field 'prompt' is required",
            },
        )
    except ValueError as exc:
        logger.warning("Gateway invalid prompt value | reason=%s", exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Invalid request body",
                "reason": str(exc),
            },
        )

    # ── Step 3: Mock LLM call ─────────────────────────────────────────────────
    raw_llm_output: str = await mock_llm_call(prompt)
    logger.info(
        "Mock LLM responded | prompt_len=%d llm_output_len=%d",
        len(prompt),
        len(raw_llm_output),
    )

    # ── Step 4: CFG validation ────────────────────────────────────────────────
    # validate_llm_output() runs two stages:
    #   a) Lark LALR(1) parse against tool_grammar.lark (structural check).
    #   b) json.loads() to deserialise the validated string into a dict.
    # Any structural violation raises OutputParsingError — caught here and
    # returned as 502 so the client knows the LLM (not the request) failed.
    try:
        tool_call: dict[str, Any] = validate_llm_output(raw_llm_output)
    except OutputParsingError as exc:
        logger.warning(
            "Gateway blocked malformed LLM output | reason=%r line=%s col=%s",
            exc.reason,
            exc.line,
            exc.column,
        )
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "LLM output structurally invalid",
                "details": exc.reason,
            },
        )

    # ── Step 5: Return validated tool call ────────────────────────────────────
    # X-GuardRail-Signature travels on the response so downstream verifiers
    # can confirm the *request* payload was signed by this gateway instance.
    logger.info(
        "Gateway delivered validated tool call | tool=%r sig_prefix=%.8s",
        tool_call.get("tool_name"),
        signature,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        headers={"X-GuardRail-Signature": signature},
        content={
            "status": "ok",
            "tool_call": tool_call,
            "signature_preview": f"{signature[:8]}...{signature[-4:]}",
        },
    )
