"""Custom exceptions for the GuardRail-AI parser subsystem."""

from __future__ import annotations


class OutputParsingError(Exception):
    """Raised when LLM output fails CFG grammar validation or deserialisation.

    GuardRail-AI's fail-closed contract guarantees this exception is raised
    (never silently swallowed) whenever the parser rejects an output.  Callers
    must catch it and route to the fallback handler — partial or unvalidated
    data is never returned.

    Attributes:
        reason:  Human-readable rejection reason, safe to surface in fallback
                 responses.  Does not contain raw input or grammar internals.
        line:    1-indexed line number of the first syntax violation, or None
                 if the error has no meaningful location (engine-level failure).
        column:  1-indexed column number of the first syntax violation, or None.
    """

    def __init__(
        self,
        reason: str,
        *,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason: str = reason
        self.line: int | None = line
        self.column: int | None = column

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"reason={self.reason!r}, "
            f"line={self.line!r}, "
            f"column={self.column!r})"
        )
