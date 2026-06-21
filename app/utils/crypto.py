"""
HMAC-SHA256 payload signing and verification.

Standard-library only (hmac + hashlib) — no external crypto dependencies,
per the project's minimal-attack-surface policy.

Key loading
-----------
GUARDRAIL_SECRET_KEY is read from the environment exactly once at module
import time and decoded from hex into raw bytes.  If the variable is absent
or the decoded key is shorter than 32 bytes (256 bits), _SECRET_KEY is set
to None and every cryptographic call fails closed (RuntimeError).

Call validate_key_at_startup() from the application lifespan so the service
refuses to accept traffic before the key is confirmed valid — never discover
a missing key on the first real request.

Canonical serialisation
-----------------------
JSON keys are sorted lexicographically and all whitespace is removed before
signing.  This ensures two payloads with identical data but different key
insertion order produce the same HMAC, which is required for consistent
verification across horizontally-scaled gateway instances.

Timing safety
-------------
verify_hmac_signature uses hmac.compare_digest (constant-time comparison)
to prevent timing-based side-channel attacks that could otherwise leak
information about the expected digest.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os

logger = logging.getLogger(__name__)

# NIST SP 800-107 §5.3.4 recommends key length ≥ output length of the hash.
# SHA-256 output is 32 bytes, so 32 bytes is the absolute minimum.
_MIN_KEY_BYTES: int = 32


# ---------------------------------------------------------------------------
# Key loading (module-level, executed once at import)
# ---------------------------------------------------------------------------

def _load_key() -> bytes | None:
    """
    Read and validate GUARDRAIL_SECRET_KEY from the environment.

    Expected format: 64 lowercase hex characters (32 raw bytes), produced by:
        python -c "import secrets; print(secrets.token_hex(32))"

    Accepts raw UTF-8 strings as a fallback, but logs a warning — hex is
    strongly preferred because it avoids encoding ambiguity.

    Returns:
        Raw key bytes if valid, None otherwise (caller must treat None as
        an irrecoverable configuration error).
    """
    raw: str = os.environ.get("GUARDRAIL_SECRET_KEY", "").strip()

    if not raw:
        logger.critical(
            "GUARDRAIL_SECRET_KEY is not set. "
            "All cryptographic operations will fail closed until the key is provided."
        )
        return None

    # Attempt hex decode first (preferred format).
    try:
        key_bytes = bytes.fromhex(raw)
    except ValueError:
        # Not valid hex — accept raw UTF-8 bytes with a warning.
        key_bytes = raw.encode("utf-8")
        logger.warning(
            "GUARDRAIL_SECRET_KEY is not hex-encoded; using raw UTF-8 bytes (%d bytes). "
            "Generate a proper key: python -c \"import secrets; print(secrets.token_hex(32))\"",
            len(key_bytes),
        )

    if len(key_bytes) < _MIN_KEY_BYTES:
        logger.critical(
            "GUARDRAIL_SECRET_KEY is too short: %d bytes provided, %d required. "
            "All cryptographic operations will fail closed.",
            len(key_bytes),
            _MIN_KEY_BYTES,
        )
        return None

    return key_bytes


# Loaded once.  The global is intentionally a module attribute so that
# validate_key_at_startup() can introspect it at lifespan time, and so
# per-call overhead is a single None-check (no env lookup, no hex decode).
_SECRET_KEY: bytes | None = _load_key()


# ---------------------------------------------------------------------------
# Internal key accessor — fail-closed gatekeeper
# ---------------------------------------------------------------------------

def _require_key() -> bytes:
    """
    Return the loaded secret key.

    Raises:
        RuntimeError: immediately if the key was not loaded successfully.
            Callers must not catch this and downgrade to unsigned operation.
    """
    if _SECRET_KEY is None:
        raise RuntimeError(
            "GUARDRAIL_SECRET_KEY is absent or invalid. "
            "Cryptographic operations cannot proceed — failing closed."
        )
    return _SECRET_KEY


# ---------------------------------------------------------------------------
# Startup validator — call from application lifespan
# ---------------------------------------------------------------------------

def validate_key_at_startup() -> None:
    """
    Confirm the secret key is present and meets the minimum length requirement.

    Raises:
        RuntimeError: if the key is missing or too short.

    Call this inside the FastAPI lifespan context so the application refuses
    to start (and refuses to serve any traffic) when improperly configured.
    """
    key = _require_key()  # raises if None
    logger.info(
        "Crypto key validated | length_bytes=%d algorithm=HMAC-SHA256",
        len(key),
    )


# ---------------------------------------------------------------------------
# Canonical payload serialisation
# ---------------------------------------------------------------------------

def canonicalize_payload(body: bytes | str) -> str:
    """
    Parse *body* as JSON and re-serialise with lexicographically sorted keys
    and no whitespace (compact UTF-8 form).

    Canonical form is the pre-image that is actually signed/verified.  It
    decouples the HMAC from key-insertion order, enabling any gateway node to
    verify a signature produced by any other node given the same shared secret.

    Args:
        body: Raw request body — bytes or str.

    Returns:
        Compact, deterministic JSON string with sorted keys.

    Raises:
        ValueError: if *body* is not valid JSON or cannot be decoded as UTF-8.
    """
    try:
        data = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Payload is not valid JSON: {exc}") from exc

    # sort_keys=True → lexicographic key ordering (deterministic across nodes).
    # separators=(",", ":") → no spaces → compact, canonical byte sequence.
    # ensure_ascii=False → preserve Unicode codepoints exactly.
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ---------------------------------------------------------------------------
# HMAC-SHA256 signing
# ---------------------------------------------------------------------------

def generate_hmac_signature(payload: str) -> str:
    """
    Compute HMAC-SHA256 over *payload* and return the lowercase hex digest.

    The caller is responsible for passing the canonical form of the payload
    (see canonicalize_payload) so that signatures are deterministic.

    Args:
        payload: The string to sign.  Should be the canonical JSON form.

    Returns:
        64-character lowercase hex string (256-bit HMAC-SHA256 digest).

    Raises:
        RuntimeError: if GUARDRAIL_SECRET_KEY is not configured (fail-closed).
    """
    key = _require_key()
    mac = hmac.new(key, payload.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()


# ---------------------------------------------------------------------------
# HMAC-SHA256 verification
# ---------------------------------------------------------------------------

def verify_hmac_signature(payload: str, signature: str) -> bool:
    """
    Verify *signature* against the HMAC-SHA256 of *payload*.

    Uses hmac.compare_digest for constant-time string comparison, preventing
    timing-based side-channel attacks that could otherwise leak bits of the
    expected digest by measuring early-exit comparison behaviour.

    Args:
        payload:   The original string that was signed (canonical JSON form).
        signature: Hex-encoded HMAC-SHA256 to verify.

    Returns:
        True only if *signature* is cryptographically valid for *payload*.
        Returns False on *any* error — key missing, bad hex, wrong length.
        Never raises (fail-closed: uncertainty → rejection).
    """
    try:
        expected = generate_hmac_signature(payload)
        # compare_digest requires both arguments to have the same type and
        # rejects mismatched lengths in constant time.
        return hmac.compare_digest(expected, signature.lower())
    except Exception:
        # Key missing, encoding error, or unexpected exception — all map to
        # rejection.  No information is returned to the caller about the cause.
        return False
