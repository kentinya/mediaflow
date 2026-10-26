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


#: The provider attributes (in the fixed order :func:`source_fingerprint` reads
#: them) that can carry an opaque content validator.  Only their *names* are
#: published as evidence; their values stay inside the fingerprint digest.
PROVIDER_VALIDATOR_NAMES = (
    "fingerprint",
    "validator",
    "etag",
    "checksum",
    "content_hash",
    "version_id",
    "generation",
)


@dataclass(frozen=True)
class SourceVersionEvidence:
    """The *binding-independent* content version of one observed source.

    :func:`source_fingerprint` answers "is this still the exact occurrence I
    reviewed?" for one ResourceLibrary binding: its digest intentionally covers
    the library identity, so two valid bindings of the same Storage produce two
    different, mutually incomparable digests for the very same file.

    Source *ownership* needs a weaker but comparable question: "is this the same
    content version, or a genuinely replaced file?".  This value carries exactly
    the observed facts that are comparable across bindings — the observed size,
    modification instant and the set of provider validators that were present —
    and nothing about the library, principal, configuration pin or plan context.
    Equal values therefore mean an unchanged source; different values are real
    evidence that the file at that path was replaced.

    A side that cannot produce this evidence is *unknown*, never "different":
    an incomparable version must not release a live ownership claim.
    """

    size: int
    modified_at: str
    validators: tuple[str, ...]


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
    for name in PROVIDER_VALIDATOR_NAMES:
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


def source_version_evidence(entry) -> SourceVersionEvidence | None:
    """The comparable content version of one bounded Storage entry.

    Pure: nothing is read beyond the attributes of the entry the caller already
    observed, and no library/principal/pin context enters the value.  ``None``
    means the observation cannot prove a comparable version at all, which keeps
    ownership conservative instead of inventing a replacement.
    """

    size = getattr(entry, "size", None)
    modified = _datetime_value(getattr(entry, "modified_at", None))
    if isinstance(size, bool) or not isinstance(size, int) or size < 0 or modified is None:
        return None
    present: list[str] = []
    for name in PROVIDER_VALIDATOR_NAMES:
        value = getattr(entry, name, None)
        if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
            if len(str(value)) <= 256:
                present.append(name)
    return SourceVersionEvidence(size, modified, tuple(sorted(present)))


def stored_source_version_evidence(evidence: object) -> SourceVersionEvidence | None:
    """Rebuild the comparable version from one persisted fingerprint evidence.

    The durable evidence document already carries the observed size, the
    modification instant and the validator *names*, so a record written under
    another ResourceLibrary binding of the same Storage stays comparable.  A
    record without that bounded evidence (a legacy row, or an unverified
    observation) answers ``None`` — unknown, never "replaced".
    """

    if not isinstance(evidence, dict):
        return None
    size = evidence.get("size")
    modified = evidence.get("modifiedAt")
    names = evidence.get("providerValidators")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        return None
    if not isinstance(modified, str) or not modified:
        return None
    if not isinstance(names, (list, tuple)) or not all(isinstance(item, str) for item in names):
        return None
    return SourceVersionEvidence(size, modified, tuple(sorted(names)))


def source_version_is_known_different(
    observed: SourceVersionEvidence | None,
    stored: SourceVersionEvidence | None,
) -> bool:
    """Whether two observations really prove a *replaced* source.

    Only comparable evidence on both sides can prove a replacement.  An unknown
    side (a legacy row, an unverified observation, a provider without any bounded
    version facts) answers ``False`` here, so it keeps the live ownership claim
    instead of releasing it for a file that was never proven to change.

    The ResourceLibrary binding, the admitting principal and the configuration pin
    deliberately take no part: they describe *context*, not content, and two valid
    bindings of one Storage must agree about one physical file.
    """

    if observed is None or stored is None:
        return False
    return observed != stored


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
    "PROVIDER_VALIDATOR_NAMES",
    "OccurrenceState",
    "SourceFingerprint",
    "SourceVersionEvidence",
    "canonical_source_path",
    "join_library_path",
    "occurrence_id_for",
    "source_fingerprint",
    "source_version_evidence",
    "source_version_is_known_different",
    "stored_source_version_evidence",
]
