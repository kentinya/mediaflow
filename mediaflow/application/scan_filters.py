"""Shared pure ResourceLibrary scan filtering and stability semantics.

This module is a deliberate *extraction*, not a second rule engine: the
``StorageScanner`` and the bounded Files discovery stage must agree on what a
configured ResourceLibrary includes, excludes and considers stable.  Keeping one
implementation of the glob/regex/extension/include/exclude/depth predicates and
one implementation of the age/stability predicate is the only way that can stay
true.

Everything here is pure: it reads a ``ResourceLibrary`` policy object and one
bounded ``StorageEntry`` (plus, for stability, the previously observed
occurrence).  It never touches Storage, never writes, never calls a Provider and
never consults the FileIndex.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath

from mediaflow.domain.library import ResourceLibrary, ScanRule, ScanRuleKind
from mediaflow.domain.storage import StorageEntry, StorageEntryType


class ScanEntryVerdict(StrEnum):
    """Why one visited entry is or is not an admissible media candidate."""

    CANDIDATE = "candidate"
    EXCLUDED_EXTENSION = "excluded_extension"
    EXCLUDED_RULE = "excluded_rule"
    NOT_INCLUDED = "not_included"
    UNSUPPORTED_TYPE = "unsupported_type"


class StabilityVerdict(StrEnum):
    """The bounded stability conclusion for one media candidate."""

    STABLE = "stable"
    UNSTABLE_AGE = "unstable_age"
    UNSTABLE_SIZE = "unstable_size"
    UNSTABLE_CHANGED = "unstable_changed"


def entry_extension(entry: StorageEntry) -> str:
    """The normalized lower-case extension of one Storage entry name."""

    return PurePosixPath(entry.name).suffix.lower().lstrip(".")


def classify_entry(
    library: ResourceLibrary,
    relative_path: str,
    entry: StorageEntry,
) -> ScanEntryVerdict:
    """Classify one *file* entry against the pinned ResourceLibrary policy.

    The relative path is the ResourceLibrary-relative path, exactly like the
    Scanner's own ``_relative`` value, so configured globs keep their existing
    meaning.
    """

    extension = entry_extension(entry)
    if extension not in library.file_extensions:
        return ScanEntryVerdict.EXCLUDED_EXTENSION
    if excluded(library.exclude_rules, relative_path, entry.name, extension, False):
        return ScanEntryVerdict.EXCLUDED_RULE
    if not included(library.include_rules, relative_path, entry.name, extension):
        return ScanEntryVerdict.NOT_INCLUDED
    return ScanEntryVerdict.CANDIDATE


def excluded_directory(
    library: ResourceLibrary,
    relative_path: str,
    entry: StorageEntry,
) -> bool:
    """Whether a directory entry is pruned by the configured exclude rules."""

    return excluded(library.exclude_rules, relative_path, entry.name, "", True)


class PrunedAncestorReason(StrEnum):
    """Why a library-root walk could never reach a directly selected entry."""

    EXCLUDED_RULE = "excluded_rule"
    NOT_INCLUDED = "not_included"
    DEPTH = "depth"


def pruned_ancestor(
    library: ResourceLibrary,
    relative_path: str,
) -> tuple[str, PrunedAncestorReason] | None:
    """The shallowest ancestor directory a library-root walk would prune.

    A directly selected file or folder must obey exactly the same root-relative
    exclude/include/depth policy as a walk that starts at the ResourceLibrary
    root.  If an ancestor directory would be pruned there, the walk could never
    reach the selection, so clicking the descendant directly must not turn it
    into a source either.  This is the one depth/rule meaning shared with the
    Scanner and the bounded walk: the caller maps the returned reason onto its
    own bounded finding vocabulary.
    """

    parts = [part for part in (relative_path or "").strip("/").split("/") if part]
    for index in range(1, len(parts)):
        ancestor = "/".join(parts[:index])
        name = parts[index - 1]
        if excluded(library.exclude_rules, ancestor, name, "", True):
            return ancestor, PrunedAncestorReason.EXCLUDED_RULE
        if not _directory_may_match(library.include_rules, ancestor):
            return ancestor, PrunedAncestorReason.NOT_INCLUDED
        # The walk prunes a child directory of ``parent`` when the parent's own
        # depth already reached the configured maximum, so a selection below
        # that child is unreachable exactly then.
        parent = "/".join(parts[: index - 1])
        depth = parent.count("/") + 1 if parent else 0
        if library.max_depth is not None and depth >= library.max_depth:
            return ancestor, PrunedAncestorReason.DEPTH
    return None


def directory_may_match(rules: tuple[ScanRule | str, ...], path: str) -> bool:
    """Whether a directory could still contain an included descendant."""

    return _directory_may_match(rules, path)


def stability_verdict(
    library: ResourceLibrary,
    entry: StorageEntry,
    *,
    now: datetime,
    previous: ObservedSource | None,
    stable_since: datetime | None,
    observed_value: str | None = None,
) -> StabilityVerdict:
    """The bounded stability conclusion for one media candidate.

    ``previous`` is the last durable observation of the *same* source in this
    discovery context.  A changed size or a changed provider fingerprint resets
    the elapsed observation interval; an unchanged observation keeps the
    previously recorded ``stable_since``.  A required stable-size interval is
    never fabricated: without a prior unchanged observation the candidate stays
    ``UNSTABLE_SIZE`` until a later observation proves the interval.
    """

    unchanged = previous is not None and previous.matches(entry, observed_value)
    if previous is not None and not unchanged:
        return stability_decision(
            library.stability_policy,
            entry,
            now=now,
            unchanged_previous=False,
            observed_since=None,
        )
    return stability_decision(
        library.stability_policy,
        entry,
        now=now,
        unchanged_previous=unchanged,
        observed_since=(
            stable_since
            or (previous.stable_since if previous is not None else None)
            or (previous.observed_at if previous is not None else None)
        )
        if unchanged
        else None,
    )


def stability_decision(
    policy,
    entry: StorageEntry,
    *,
    now: datetime,
    unchanged_previous: bool,
    observed_since: datetime | None,
) -> StabilityVerdict:
    """The shared age/stability predicate used by the Scanner and discovery.

    ``unchanged_previous`` is the caller's own proof that the last durable
    observation of this source had the same observable identity (the Scanner
    proves it from the FileIndex occurrence; discovery proves it from its own
    durable observation record).  ``observed_since`` is the timestamp from which
    a required stable-size interval is measured, and is only meaningful when
    ``unchanged_previous`` holds.
    """

    age = max(0.0, (now - entry.modified_at).total_seconds())
    required_age = max(policy.minimum_age_seconds, policy.modified_threshold_seconds)
    if age < required_age:
        return StabilityVerdict.UNSTABLE_AGE
    if policy.stable_size_duration_seconds == 0:
        return StabilityVerdict.STABLE
    if not unchanged_previous or observed_since is None:
        # A required stable-size duration is never fabricated from age alone.
        return StabilityVerdict.UNSTABLE_SIZE
    elapsed = max(0.0, (now - observed_since).total_seconds())
    if elapsed < policy.stable_size_duration_seconds:
        return StabilityVerdict.UNSTABLE_SIZE
    return StabilityVerdict.STABLE


def stability_wait_seconds(
    library: ResourceLibrary,
    entry: StorageEntry,
    *,
    now: datetime,
    unchanged_previous: bool,
    observed_since: datetime | None,
) -> float:
    """The bounded real time still required before this source can be re-proven.

    A source that is not yet proven stable must be *re-observed* later, never
    immediately: reclaiming it in a tight loop would spin, consume the durable
    traversal budget while doing no traversal and starve every other resident
    command.  This returns the remaining genuine interval for the exact reason
    the source is still waiting, so a waiting discovery becomes claimable again
    only when an observation could actually change the verdict.

    The value is never fabricated and never negative: when no interval has been
    established yet, the next observation must itself be separated from this one
    by the full configured stable-size duration before it can prove stability.
    """

    policy = library.stability_policy
    required_age = max(policy.minimum_age_seconds, policy.modified_threshold_seconds)
    age = max(0.0, (now - entry.modified_at).total_seconds())
    if age < required_age:
        return required_age - age
    if policy.stable_size_duration_seconds == 0:
        return 0.0
    if not unchanged_previous or observed_since is None:
        # The interval starts now: the next observation has to be a full
        # duration later to prove an unchanged stable-size interval.
        return float(policy.stable_size_duration_seconds)
    elapsed = max(0.0, (now - observed_since).total_seconds())
    return max(0.0, float(policy.stable_size_duration_seconds) - elapsed)


@dataclass(frozen=True)
class ObservedSource:
    """One bounded durable observation of a real Storage source."""

    path: str
    size: int
    modified_at: datetime
    fingerprint: str | None
    observed_at: datetime
    stable_since: datetime | None = None

    def matches(self, entry: StorageEntry, observed_value: str | None = None) -> bool:
        """Whether a fresh observation is the same unchanged occurrence.

        ``observed_value`` is the *computed* source fingerprint of the fresh
        entry, exactly as the Scanner compares it against the previous index
        occurrence.  Size and modification time must be unchanged, and a
        previously verified digest must still match; a provider that publishes
        no validator still compares by its observable size/time identity.
        """

        if entry.size != self.size or entry.modified_at != self.modified_at:
            return False
        if self.fingerprint is None:
            return True
        return observed_value is not None and observed_value == self.fingerprint


def included(rules: tuple[ScanRule | str, ...], path: str, filename: str, extension: str) -> bool:
    return not rules or any(_matches(rule, path, filename, extension, False) for rule in rules)


def excluded(
    rules: tuple[ScanRule | str, ...],
    path: str,
    filename: str,
    extension: str,
    directory: bool,
) -> bool:
    return any(_matches(rule, path, filename, extension, directory) for rule in rules)


def _directory_may_match(rules: tuple[ScanRule | str, ...], path: str) -> bool:
    if not rules:
        return True
    for raw_rule in rules:
        rule = raw_rule if isinstance(raw_rule, ScanRule) else ScanRule(ScanRuleKind.GLOB, raw_rule)
        if rule.kind is ScanRuleKind.REGEX:
            return True
        if rule.kind in {ScanRuleKind.FILENAME, ScanRuleKind.EXTENSION}:
            return True
        pattern = rule.pattern.lstrip("/")
        fixed = re.split(r"[*?[{]", pattern, maxsplit=1)[0].rstrip("/")
        if (
            not fixed
            or fixed == path
            or fixed.startswith(path + "/")
            or path.startswith(fixed + "/")
        ):
            return True
    return False


def _matches(
    raw_rule: ScanRule | str, path: str, filename: str, extension: str, directory: bool
) -> bool:
    rule = raw_rule if isinstance(raw_rule, ScanRule) else ScanRule(ScanRuleKind.GLOB, raw_rule)
    pattern = rule.pattern
    if rule.kind is ScanRuleKind.PATH:
        return path == pattern.strip("/")
    if rule.kind is ScanRuleKind.FILENAME:
        return filename == pattern
    if rule.kind is ScanRuleKind.EXTENSION:
        return extension.lower() == pattern.lower().lstrip(".")
    if rule.kind is ScanRuleKind.DIRECTORY:
        return directory and (path == pattern.strip("/") or filename == pattern.strip("/"))
    if rule.kind is ScanRuleKind.REGEX:
        return re.search(pattern, path) is not None
    normalized = path.strip("/")
    candidates = (normalized, filename, "/" + normalized)
    patterns = (pattern, pattern.removeprefix("**/"))
    if directory:
        for candidate_pattern in patterns:
            base = candidate_pattern.removesuffix("/**").rstrip("/")
            if base != candidate_pattern and normalized == base:
                return True
    return any(
        fnmatch.fnmatchcase(candidate, candidate_pattern)
        for candidate in candidates
        for candidate_pattern in patterns
    )


def entry_is_symlink(entry: StorageEntry) -> bool:
    return entry.entry_type is StorageEntryType.SYMLINK
