"""Pure canonical integrity rules for a persisted managed configuration document.

A managed Active revision is only trustworthy when its persisted ``schema_version``
is one this build understands and its stored ``digest`` is the canonical digest of
its own payload.  Those two rules are pure and authority-free, so they live here
rather than inside a service: the ordinary read-write configuration repository, the
read-only operator reader and any future consumer must all reach the *same*
verdict for the same bytes.

Nothing here reads or writes a database, opens Storage, calls a Provider or
persists anything.
"""

from __future__ import annotations

import hashlib
import json

#: The only managed configuration document schema this build can safely consume.
MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION = 1


def canonical_document_digest(document: dict[str, object]) -> str:
    """Return the deterministic SHA-256 digest of one configuration document."""

    encoded = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION",
    "canonical_document_digest",
]
