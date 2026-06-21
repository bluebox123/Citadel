"""
CFG parser engine for LLM tool-call output validation.

Module-level initialisation (at import time):
  - Grammar file is read once from disk.
  - Lark LALR(1) parser is compiled once.

This mirrors the eager-init pattern in app/utils/crypto.py (_SECRET_KEY loaded
at import) so misconfiguration is discovered at process start, not on the first
live request.  If the grammar file is missing or malformed, module import raises
immediately — fail-fast before serving any traffic.

Public API: validate_llm_output(raw_output) -> dict
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any

from lark import Lark
from lark.exceptions import UnexpectedCharacters, UnexpectedInput, UnexpectedToken

from app.parser.exceptions import OutputParsingError

logger = logging.getLogger(__name__)

# ── Grammar & parser — built once at module import ────────────────────────────

_GRAMMAR_PATH: pathlib.Path = pathlib.Path(__file__).parent / "tool_grammar.lark"

# Maximum characters of raw LLM output to include in log lines.
# Never log the full payload — it may contain sensitive data.
_LOG_PREVIEW_LEN: int = 200


def _build_parser() -> Lark:
    """Read grammar file and compile the LALR(1) parser.

    Uses Lark's contextual lexer, which resolves terminal ambiguities (e.g.
    TOOL_NAME_KEY vs ESCAPED_STRING) from parser state rather than regex
    priority alone — giving deterministic, single-token look-ahead behaviour
    in every parser state.

    Raises:
        FileNotFoundError: grammar file absent (deployment / packaging error).
        lark.exceptions.GrammarError: grammar is syntactically malformed.

    Both exceptions propagate at module import time, not at parse time.
    """
    grammar_text = _GRAMMAR_PATH.read_text(encoding="utf-8")
    return Lark(grammar_text, parser="lalr", lexer="contextual")


# Module-level singleton.  Grammar errors surface here, not per-request.
_PARSER: Lark = _build_parser()


# ── Startup validator ─────────────────────────────────────────────────────────

def validate_parser_at_startup() -> None:
    """Assert the CFG parser is ready; log confirmation at INFO level.

    Called from the FastAPI lifespan hook so grammar compilation errors surface
    at process start, not on the first request.  Mirrors validate_key_at_startup()
    in app/utils/crypto.py — both enforce the fail-fast startup contract.

    Raises:
        RuntimeError: if _PARSER is somehow None (should not happen given
            module-level initialisation, but guards against import-order bugs).
    """
    if _PARSER is None:
        raise RuntimeError("CFG parser failed to initialise — grammar file missing or malformed")
    logger.info(
        "CFG parser validated | grammar=%s parser=LALR(1) lexer=contextual",
        _GRAMMAR_PATH.name,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_lark_error(
    exc: UnexpectedInput,
) -> tuple[int | None, int | None, str]:
    """Extract (line, column, internal_detail) from a Lark parse exception.

    Returns a detail string intended for *internal logs only* — it may contain
    grammar terminal names and raw token values, which are not exposed to
    callers via OutputParsingError.reason.

    Args:
        exc: Any UnexpectedInput subclass (UnexpectedToken, UnexpectedCharacters).

    Returns:
        Tuple of (line, column, detail_for_log).
    """
    line: int | None = getattr(exc, "line", None)
    column: int | None = getattr(exc, "column", None)

    if isinstance(exc, UnexpectedToken):
        token_str = str(exc.token)
        if not token_str:
            # LALR(1) encodes unexpected EOF as UnexpectedToken with $END token.
            expected = sorted(getattr(exc, "expected", None) or [])
            detail = f"unexpected end of input; expected one of {expected}"
        else:
            expected = sorted(getattr(exc, "expected", None) or [])
            detail = f"unexpected token {token_str!r}; expected one of {expected}"
    elif isinstance(exc, UnexpectedCharacters):
        # The bad character is at (line, column); no .token attribute on this subtype.
        detail = f"unexpected character at line {line}, col {column}"
    else:
        detail = f"{type(exc).__name__} at line {line}, col {column}"

    return line, column, detail


# ── Public API ────────────────────────────────────────────────────────────────

def validate_llm_output(raw_output: str) -> dict[str, Any]:
    """Parse and validate a raw LLM tool-call string against the CFG grammar.

    Two-stage pipeline:
      1. Lark LALR(1) parse — structural validation against tool_grammar.lark.
         Rejects: conversational prefix, trailing commas, wrong key order,
         non-object arguments value, extra top-level keys, unescaped quotes.
      2. json.loads() — deserialises the grammar-validated string into a dict.
         Step 2 cannot fail if step 1 passed; any failure here is an internal
         error and is still treated fail-closed (raises OutputParsingError).

    Args:
        raw_output: Raw string emitted by the LLM.  May have leading/trailing
            whitespace; any other prefix causes an immediate parse failure per
            grammar design (%ignore WS strips whitespace, nothing else).

    Returns:
        Validated tool-call dict with guaranteed keys ``"tool_name"`` (str)
        and ``"arguments"`` (dict).  The returned dict is safe to pass to the
        transformer for semantic validation (whitelist check, schema check).

    Raises:
        OutputParsingError: on any structural or deserialisation failure.
            ``.line`` and ``.column`` are set when location data is available.
    """
    preview = raw_output[:_LOG_PREVIEW_LEN]

    # ── Stage 1: Grammar validation ───────────────────────────────────────────
    try:
        _PARSER.parse(raw_output)

    except UnexpectedInput as exc:
        line, column, log_detail = _extract_lark_error(exc)

        # Internal log: full error detail (grammar terminal names, token values).
        # These stay in our logs; they are NOT forwarded to the caller.
        logger.warning(
            "Parser rejected LLM output | %s | preview=%.200r",
            log_detail,
            preview,
        )

        # Public-facing reason: location only, no grammar internals.
        if line is not None:
            public_reason = f"Syntax error at line {line}, column {column}"
        else:
            public_reason = "Syntax error: malformed tool-call output"

        raise OutputParsingError(public_reason, line=line, column=column) from exc

    except Exception as exc:
        # Grammar engine error, internal Lark error, OOM — reject, never fall through.
        logger.error(
            "Parser engine error | type=%s | preview=%.200r",
            type(exc).__name__,
            preview,
        )
        raise OutputParsingError("Parser engine error — output rejected") from exc

    # ── Stage 2: Deserialisation ──────────────────────────────────────────────
    # The grammar guarantees valid JSON; json.loads() should be infallible here.
    # Wrapping in try/except is belt-and-suspenders: if an impossible state
    # occurs, we still fail closed rather than returning unvalidated data.
    try:
        result: dict[str, Any] = json.loads(raw_output)
    except Exception as exc:
        logger.error(
            "json.loads() failed after grammar validation — impossible state | "
            "type=%s | preview=%.200r",
            type(exc).__name__,
            preview,
        )
        raise OutputParsingError(
            "Deserialisation error after grammar validation"
        ) from exc

    logger.debug(
        "Parser accepted output | tool=%r arg_keys=%s",
        result.get("tool_name"),
        sorted(result.get("arguments", {}).keys()),
    )
    return result
