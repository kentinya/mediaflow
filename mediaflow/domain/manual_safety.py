"""Small, shared safety helpers for durable operator-facing evidence.

Manual-organize and pipeline-evidence records can be rendered after a restart
and can therefore contain text that did not originate in the current request.
Keep their redaction rules in the domain layer so application, persistence and
transport projections use the same definition of a secret-free record.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:api[_-]?keys?|password|passwd|secret|tokens?|authorization|cookies?)\b"
    r"\s*[:=]\s*)(?:(?:bearer|basic)\s+)?"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_AUTHORIZATION_HEADER = re.compile(
    r"(?i)(\bauthorization\b\s*:\s*)(?:(?:bearer|basic)\s+)?"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)


def redact_evidence_text(value: object, *, limit: int | None = None) -> str:
    """Return bounded evidence text with complete credential values replaced.

    The optional auth scheme is consumed together with the credential.  This
    is important for ``Authorization: Bearer <secret>``: replacing only the
    first token would still expose the credential tail.
    """

    text = str(value)
    if limit is not None:
        text = text[:limit]
    text = _AUTHORIZATION_HEADER.sub(r"\1[redacted]", text)
    return _SECRET_ASSIGNMENT.sub(r"\1[redacted]", text)


def contains_manual_secret(value: object) -> bool:
    """Whether text contains a credential-shaped manual evidence value."""

    text = str(value)
    return bool(_AUTHORIZATION_HEADER.search(text) or _SECRET_ASSIGNMENT.search(text))


def redact_evidence_value(value: object) -> object:
    """Recursively redact JSON-compatible evidence without changing shape."""

    if isinstance(value, str):
        return redact_evidence_text(value)
    if isinstance(value, Mapping):
        return {key: redact_evidence_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_evidence_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_evidence_value(item) for item in value)
    return value


# Compatibility names retained for the accepted manual-organize contract.  Both
# journeys deliberately use the same implementation and credential patterns.
redact_manual_text = redact_evidence_text
redact_manual_value = redact_evidence_value


def safe_manual_error(value: object, fallback: str) -> str:
    """Return a short, secret-free error suitable for a manual projection."""

    return redact_manual_text(value, limit=512) or fallback
