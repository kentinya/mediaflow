"""Bounded, source-linked review references.

One durable review (recognition, metadata, metadata correction, classification or
conflict) can be reached from the exact source it was raised for.  This is a
read-only projection used by the detail/export surfaces; it is not a file
catalog and carries no processing disposition.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileReviewLink:
    kind: str
    review_id: str
    status: str
    task_id: str
    item_id: str | None = None


__all__ = ["FileReviewLink"]
