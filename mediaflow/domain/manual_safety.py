"""Small, shared safety helpers for durable operator-facing evidence.

Manual-organize and pipeline-evidence records can be rendered after a restart
and can therefore contain text that did not originate in the current request.
Keep their redaction rules in the domain layer so application, persistence and
transport projections use the same definition of a secret-free record.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

# Absolute host/adapter paths, UNC roots and scheme endpoints in durable
# evidence text would expose the deployment's host or adapter layout, so the
# bounded projection fails closed on these shapes.  The shapes are open-ended
# (POSIX directories without a dotted file name, Windows adapter roots, any
# ``scheme://`` endpoint, UNC roots), so detection is deliberately broader
# than any single spelling and the whole field is replaced: a false positive
# only costs benign detail, while a false negative would leak a host value.
_EVIDENCE_PATH_SHAPES = (
    re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://"),
    re.compile(r"(?:^|[\s(\[\"'])/[^\s\"']"),
    re.compile(r"\b[A-Za-z]:[\\/]"),
    re.compile(r"\\\\"),
)

#: The bounded marker published in place of a value that is not a provably
#: safe, Storage-relative identity.
_IDENTITY_PATH_REDACTION = "[redacted-path]"

#: The bound on one published identity value.  It mirrors the bounded
#: operator-text limit so one value has exactly one public form.
_MAX_IDENTITY_TEXT = 512

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


def contains_evidence_path_shape(text: str) -> bool:
    """Whether text still contains a forbidden host/adapter path shape."""

    return any(pattern.search(text) is not None for pattern in _EVIDENCE_PATH_SHAPES)


def bounded_identity_path(value: object | None) -> str | None:
    """Project a persisted Storage-relative identity or fail closed.

    The Operations projection assumes source/destination identities are
    Storage-relative, but a legacy or externally written row can hold an
    absolute host/adapter root, a UNC root, a private endpoint or a
    credential-shaped value in the same column.  Only a provably relative
    identity is published; anything else is replaced with the bounded
    redaction marker.

    This is the single definition of the public form of one scope/identity
    value: the application API publishes through it and the persistence
    search boundary derives its searchable text from it, so a value the
    projection hides can never still be matched by a repository search.
    """

    if not isinstance(value, str):
        return _IDENTITY_PATH_REDACTION if value is not None else None
    text = value.strip()
    segments = text.replace("\\", "/").split("/")
    if (
        not text
        or len(text) > _MAX_IDENTITY_TEXT
        or text.startswith(("/", "\\", "~"))
        or re.match(r"^[A-Za-z]:", text) is not None
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", text) is not None
        or ".." in segments
        or redact_manual_text(text) != text
        or contains_evidence_path_shape(text)
    ):
        return _IDENTITY_PATH_REDACTION
    return text


def searchable_identity_text(value: object | None) -> str | None:
    """The text one persisted identity value may contribute to a search.

    Exactly the publicly published form of the value: a value that
    :func:`bounded_identity_path` would replace with the redaction marker
    contributes nothing at all, so a substring search (including a READ-only
    principal's search) can never discover content the public projection
    hides.  ``None`` and non-text values contribute nothing either.
    """

    published = bounded_identity_path(value)
    if published is None or published == _IDENTITY_PATH_REDACTION:
        return None
    return published
