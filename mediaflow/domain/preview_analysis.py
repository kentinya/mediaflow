"""Internal control-flow exceptions shared by the organize Preview analysis chain.

This module deliberately keeps only minimal domain exceptions used by the
organized Preview analysis chain (``manual_organize_preview.py``,
``media_discovery.py``, etc.).  It is not part of any independent Preview
product: no durable analysis record, no Worker, no claim/lease, no publication,
and no separate queue exist here.
"""

from __future__ import annotations


class PreviewAnalysisConflict(Exception):
    """One bounded optimistic-conflict signal during Preview analysis reconciliation."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.details = dict(details or {})


class PreviewAnalysisControlRequested(Exception):
    """Internal signal to stop an in-flight zero-mutation analysis at a boundary."""

    def __init__(self, action: str) -> None:
        if action not in {"pause", "cancel"}:
            raise ValueError("preview analysis control action is invalid")
        super().__init__(action)
        self.action = action


__all__ = ["PreviewAnalysisConflict", "PreviewAnalysisControlRequested"]
