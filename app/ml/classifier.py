"""
ML-based harmful content classifier.

Loads a pre-trained TF-IDF + Logistic Regression pipeline from model.pkl
eagerly at module import time — the same pattern used by app.utils.crypto
(_SECRET_KEY) and app.parser.engine (_PARSER).  This ensures the model is
available in tests and environments where the FastAPI lifespan is not run.

Fail-closed design: if the model is missing or corrupt, classify() returns
None and the firewall falls back to rule-based detection only (no crash).
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).parent / "model.pkl"

# Confidence threshold: only flag as harmful when the model is this sure.
# 0.70 balances precision and recall for TF-IDF + LR calibration.  False
# positives are still undesirable, but the rule-based firewall handles
# obvious injection patterns so the ML layer targets semantic threats.
_HARMFUL_THRESHOLD: float = 0.65


class MLDecision(NamedTuple):
    is_harmful: bool
    confidence: float   # P(harmful) in [0, 1]
    category: str       # "harmful" | "safe"


# ---------------------------------------------------------------------------
# Eager module-level load (mirrors crypto._SECRET_KEY / parser._PARSER)
# ---------------------------------------------------------------------------

def _try_load():  # type: ignore[return]
    """
    Load the trained sklearn pipeline from disk.
    Called once at module import; never raises — returns (None, False) on any
    failure so the server can still start without an ML model.
    """
    if not _MODEL_PATH.exists():
        logger.warning(
            "ML model not found at %s — run scripts/train_classifier.py first. "
            "Falling back to rule-based detection only.",
            _MODEL_PATH,
        )
        return None, False

    try:
        with _MODEL_PATH.open("rb") as fh:
            pipeline = pickle.load(fh)  # noqa: S301  (trusted internal artifact)
        logger.info("ML harmful-content classifier loaded from %s", _MODEL_PATH)
        return pipeline, True
    except Exception as exc:
        logger.error("Failed to load ML model: %s — ML layer disabled", exc)
        return None, False


_pipeline, _model_loaded = _try_load()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_model() -> bool:
    """
    Called from the FastAPI lifespan for a startup log line.
    The model is already loaded at import time; this just reports status.
    """
    if _model_loaded:
        logger.info("ML classifier ready (loaded at import from %s)", _MODEL_PATH)
    else:
        logger.warning(
            "ML classifier not available — run scripts/train_classifier.py "
            "to enable the ML detection layer."
        )
    return _model_loaded


def is_loaded() -> bool:
    return _model_loaded


def classify(text: str) -> MLDecision | None:
    """
    Classify *text* as 'harmful' or 'safe'.

    Returns None when the model is not loaded (firewall continues with
    rule-based check only — graceful degradation, never a hard failure).
    """
    if not _model_loaded or _pipeline is None:
        return None

    try:
        proba = _pipeline.predict_proba([text])[0]
        classes = list(_pipeline.classes_)
        harmful_idx = classes.index("harmful")
        confidence = float(proba[harmful_idx])
        is_harmful = confidence >= _HARMFUL_THRESHOLD
        return MLDecision(
            is_harmful=is_harmful,
            confidence=confidence,
            category="harmful" if is_harmful else "safe",
        )
    except Exception as exc:
        logger.error("ML classify() raised unexpectedly: %s", exc)
        return None
