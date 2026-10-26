"""Bounded, secret-free source-occurrence evidence.

This module owns only the value objects and deterministic helpers that an
*explicit* unit of work (a Task item, a preparation, a manual intent) uses to
prove that the source it reviewed is still the same source.  It is deliberately
not a file catalog: nothing here lists, enumerates, remembers or reconciles a
Library, and no long-lived per-file record is derived from it.

The evidence is always produced from one bounded Storage listing/stat entry:

* the observable identity is ``storage`` + ``library`` + ``relative path``,
  plus the provider's own size/modification facts and any stable opaque
  validator the provider publishes;
* the fingerprint is a SHA-256 over exactly those bounded facts, so an unchanged
  entry yields the same value and any change yields a different one;
* the occurrence identity names one *specific observed content state* at that
  path, so replaying an older reviewed occurrence can never match a replaced
  file at the same path.

This module never reads Storage, never writes, never calls a Provider and never
persists anything.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class OccurrenceState(StrEnum):
    """Whether one observed source occurrence could be proven exactly."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    LEGACY = "legacy"


@dataclass(frozen=True)
class SourceFingerprint:
    """A bounded, secret-free fingerprint obtained from a Storage listing entry."""

    algorithm: str
    value: str | None
    evidence: dict[str, Any]
    state: OccurrenceState

    def document(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "value": self.value,
            "evidence": dict(self.evidence),
            "state": self.state.value,
        }


def source_fingerprint(storage_id: str, resource_library_id: str, entry) -> SourceFingerprint:
    """Build deterministic evidence from a bounded Storage stat/list entry.

    Callers intentionally never call ``read``.  Some Storage providers expose a
    stable opaque validator (ETag, checksum, version, or generation); those
    values are included in the hash but never emitted as evidence.  Unknown
    provider attributes are ignored so a provider cannot smuggle arbitrary or
    secret data into the evidence record.
    """

    evidence: dict[str, Any] = {"source": "storage_entry", "providerValidators": []}
    canonical: dict[str, Any] = {
        "storageId": storage_id,
        "resourceLibraryId": resource_library_id,
        "path": getattr(entry, "path", None),
        "filename": getattr(entry, "name", None),
        "size": getattr(entry, "size", None),
        "modifiedAt": _datetime_value(getattr(entry, "modified_at", None)),
    }
    valid = (
        isinstance(storage_id, str)
        and bool(storage_id)
        and isinstance(resource_library_id, str)
        and bool(resource_library_id)
        and isinstance(canonical["path"], str)
        and bool(canonical["path"])
        and isinstance(canonical["filename"], str)
        and isinstance(canonical["size"], int)
        and not isinstance(canonical["size"], bool)
        and canonical["size"] >= 0
        and canonical["modifiedAt"] is not None
    )
    validators: dict[str, str | int] = {}
    for name in (
        "fingerprint",
        "validator",
        "etag",
        "checksum",
        "content_hash",
        "version_id",
        "generation",
    ):
        value = getattr(entry, name, None)
        if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
            text = str(value)
            if len(text) <= 256:
                validators[name] = value
                evidence["providerValidators"].append(name)
    canonical["providerValidators"] = validators
    if not valid:
        return SourceFingerprint(
            "storage-entry-sha256",
            None,
            {
                "source": "storage_entry",
                "providerValidators": tuple(evidence["providerValidators"]),
            },
            OccurrenceState.UNVERIFIED,
        )
    digest = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    evidence.update(
        {
            "size": canonical["size"],
            "modifiedAt": canonical["modifiedAt"],
            "bounded": True,
        }
    )
    return SourceFingerprint("storage-entry-sha256", digest, evidence, OccurrenceState.VERIFIED)


def canonical_source_path(root_path: str | None, relative_path: str) -> str:
    """The exact confined Storage-relative path of one library-relative source.

    Two valid ResourceLibrary bindings of the same Storage expose the same
    concrete file under different library-relative paths (``One.mkv`` from a root
    at ``Movies`` and ``Movies/One.mkv`` from the Storage root).  Verified source
    ownership must compare the file itself, so every identity boundary converts to
    this one canonical form instead of comparing incomparable relative strings.
    Distinct roots still yield distinct values, so equal relative names in
    genuinely different subtrees never collide.  Pure: no Storage access.

    The input is *always* library-relative: :func:`join_library_path` is the one
    join the Storage adapters themselves use, and the result is therefore the
    same value the provider reports for that entry.  A textual ``startswith``
    shortcut is deliberately *not* used: with a root of ``Movies`` and a
    library-relative ``Movies/One.mkv`` under a Storage whose real file is
    ``Movies/Movies/One.mkv`` the shortcut would return the unprefixed (and
    therefore wrong) path and let the same concrete source be admitted twice
    under two bindings.  A caller that already holds a Storage-relative value
    must pass an empty root instead of relying on prefix inference.
    """

    return join_library_path(root_path, relative_path)


def join_library_path(root_path: str | None, relative_path: str) -> str:
    """Join one ResourceLibrary root and one library-relative path, exactly once.

    This mirrors the Storage adapters' own join (``PurePosixPath(root) / value``
    with empty parts dropped), so an identity computed here and a provider path
    observed from real Storage agree on the same concrete entry.
    """

    parts = [part for part in (root_path or "").strip("/").split("/") if part]
    parts.extend(part for part in (relative_path or "").strip("/").split("/") if part)
    return "/".join(parts)


def occurrence_id_for(
    storage_id: str, resource_library_id: str, path: str, fingerprint: str | None
) -> str:
    """The exact identity of one observed content state at one source path."""

    value = json.dumps(
        {
            "storageId": storage_id,
            "resourceLibraryId": resource_library_id,
            "path": path,
            "fingerprint": fingerprint,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "occ-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:40]


def _datetime_value(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


__all__ = [
    "OccurrenceState",
    "SourceFingerprint",
    "canonical_source_path",
    "join_library_path",
    "occurrence_id_for",
    "source_fingerprint",
]
