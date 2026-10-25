"""Shared pure ResourceLibrary scan filtering and stability semantics.

This module is a deliberate *extraction*, not a second rule engine: the
``StorageScanner`` and the bounded Files discovery stage must agree on what a
configured ResourceLibrary includes, excludes and considers stable.  Keeping one
implementation of the glob/regex/extension/include/exclude/depth predicates and
one implementation of the age/stability predicate is the only way that can stay
true.

Everything here is pure: it reads a ``ResourceLibrary`` policy object and one
bounded ``StorageEntry`` (plus, for stability, the caller's own previously
observed occurrence).  It never touches Storage, never writes, never calls a
Provider and never consults any file catalog.
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


#: The configured temporary/download suffixes.  A file still carrying one of
#: these suffixes is an *explicit* exclusion for every entrance (automatic walk
#: and deliberate manual selection alike): it is by definition still being
#: written, so it is never a stable source.
TEMPORARY_SUFFIXES = (".part", ".tmp", ".download", ".crdownload", ".!qb")


class ManualEntryVerdict(StrEnum):
    """Why one *deliberately selected* source is or is not a legal manual source.

    A direct Files selection is a human decision, not a scan.  The configured
    extension allowlist, include rules and non-extension exclude/match rules
    answer the different question "would a library walk have offered this?",
    so they cannot veto a *directly named* file.  What a deliberate selection
    still obeys is what the operator explicitly configured as an *exclusion of
    that exact kind*: a configured extension exclusion and the built-in
    temporary/download suffixes.

    ``EXCLUDED_PRIMARY_EXTENSION`` is the one folder-expansion rule: inside a
    deliberately selected folder the configured primary-media extension set
    (default video) still decides which files are primaries, exactly as RO-2
    requires, while every other automatic include/exclude/match condition loses
    its veto there.
    """

    ADMITTED = "admitted"
    EXCLUDED_TEMPORARY = "excluded_temporary"
    EXCLUDED_EXTENSION = "excluded_extension"
    EXCLUDED_PRIMARY_EXTENSION = "excluded_primary_extension"


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


def classify_manual_file_selection(
    library: ResourceLibrary,
    relative_path: str,
    entry: StorageEntry,
) -> ManualEntryVerdict:
    """Classify one deliberately selected *file* against explicit exclusions only.

    The difference from :func:`classify_entry` is deliberate and is the whole
    point of the Slice46 amendment: an operator who clicks one exact file has
    already made the inclusion decision a walk would otherwise make.  A suffix
    that is merely absent from ``file_extensions``, an include-rule miss and a
    non-extension exclude/match rule therefore keep their automatic meaning for
    folder expansion without becoming additional manual vetoes.

    ``relative_path`` is still accepted so a future explicit path exclusion can
    reuse this boundary without a second signature; the current rule kinds that
    veto a deliberate selection are the extension and temporary-suffix ones.
    """

    if entry.name.lower().endswith(TEMPORARY_SUFFIXES):
        return ManualEntryVerdict.EXCLUDED_TEMPORARY
    if extension_exclusion_rule(library, entry):
        return ManualEntryVerdict.EXCLUDED_EXTENSION
    return ManualEntryVerdict.ADMITTED


def classify_manual_folder_entry(
    library: ResourceLibrary,
    relative_path: str,
    entry: StorageEntry,
) -> ManualEntryVerdict:
    """Classify one file found by expanding a *deliberately selected* folder.

    RO-2 keeps exactly one automatic file filter inside a deliberate folder
    expansion: the ResourceLibrary's configured primary-media extension set
    (video by default).  That is what stops pictures, subtitles and NFO files
    from becoming independent primaries merely because they sat in the selected
    folder.  The include rules, the non-extension exclude/match rules and the
    "is this suffix in the allowlist" short-circuit keep their unchanged
    automatic meaning for Scanner/definition-bound walks without becoming extra
    manual vetoes here.

    Explicit exclusions still apply unchanged: the built-in temporary/download
    suffixes and a configured *extension* exclude rule.  ``relative_path`` is
    accepted for the same reason as in :func:`classify_manual_file_selection`.
    """

    if entry.name.lower().endswith(TEMPORARY_SUFFIXES):
        return ManualEntryVerdict.EXCLUDED_TEMPORARY
    if extension_exclusion_rule(library, entry):
        return ManualEntryVerdict.EXCLUDED_EXTENSION
    if entry_extension(entry) not in library.file_extensions:
        return ManualEntryVerdict.EXCLUDED_PRIMARY_EXTENSION
    return ManualEntryVerdict.ADMITTED


def extension_exclusion_rule(
    library: ResourceLibrary,
    entry: StorageEntry,
) -> ScanRule | None:
    """The configured *extension* exclude rule that excludes this entry, if any."""

    extension = entry_extension(entry)
    for raw_rule in library.exclude_rules:
        rule = raw_rule if isinstance(raw_rule, ScanRule) else ScanRule(ScanRuleKind.GLOB, raw_rule)
        if rule.kind is ScanRuleKind.EXTENSION and rule.pattern.lower().lstrip(".") == extension:
            return rule
    return None


def excluded_directory(
    library: ResourceLibrary,
    relative_path: str,
    entry: StorageEntry,
) -> bool:
    """Whether a directory entry is pruned by the configured exclude rules."""

    return excluded(library.exclude_rules, relative_path, entry.name, "", True)


@dataclass(frozen=True)
class ManualFolderPolicy:
    """The pinned policy one deliberate folder expansion applies.

    It is a value, not a second rule engine: :meth:`file_verdict` and
    :meth:`may_enter_directory` are the only two questions the bounded walk asks
    per entry, and both delegate to the shared predicates above.  ``automatic``
    selects the original Scanner-equal semantics so an ordinary library walk, a
    definition-bound Run once and a recovery preparation keep exactly the
    filtering they had.
    """

    library: ResourceLibrary
    automatic: bool = True

    def file_verdict(
        self, relative_path: str, entry: StorageEntry, *, direct: bool
    ) -> ManualEntryVerdict | ScanEntryVerdict:
        """The verdict for one observed file.

        A directly named file is judged by :func:`classify_manual_file_selection`
        and a file reached by expanding a selected folder by
        :func:`classify_manual_folder_entry`; an automatic walk keeps
        :func:`classify_entry` unchanged.
        """

        if direct:
            return classify_manual_file_selection(self.library, relative_path, entry)
        if self.automatic:
            return classify_entry(self.library, relative_path, entry)
        return classify_manual_folder_entry(self.library, relative_path, entry)

    def may_enter_directory(self, relative_path: str, entry: StorageEntry) -> bool:
        """Whether the walk may descend into one observed child directory.

        A deliberate folder expansion still honours the hard traversal bounds
        (configured depth is checked by the caller, the Task safety depth inside
        the walk) but no longer applies the automatic exclude/include rule vetoes
        to the selected tree.
        """

        if self.automatic:
            if excluded_directory(self.library, relative_path, entry):
                return False
            return directory_may_match(self.library.include_rules, relative_path)
        return True


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

    ``unchanged_previous`` is the caller's own proof that its last durable
    observation of this source had the same observable identity.  Every caller
    proves it from its own persisted observation of the exact work it is
    continuing, so no global catalog is consulted.  ``observed_since`` is the
    timestamp from which a required stable-size interval is measured, and is
    only meaningful when ``unchanged_previous`` holds.
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
    """One bounded durable observation of a real Storage source.

    A live walk builds it from the entry facts it just read.  A later process
    that only has the work's own persisted evidence (occurrence/fingerprint and
    the instant this work first observed the source) builds the same shape with
    :meth:`from_persisted`, where ``size``/``modified_at`` are unknown and the
    identity comparison falls back to the persisted fingerprint.
    """

    path: str
    size: int | None
    modified_at: datetime | None
    fingerprint: str | None
    observed_at: datetime
    stable_since: datetime | None = None

    @classmethod
    def from_persisted(
        cls, path: str, fingerprint: str | None, observed_at: datetime
    ) -> ObservedSource:
        """Reconstruct this work's own durable observation without a live read.

        The interval is measured from the instant this explicit work first
        observed the exact source, so a later real observation can prove the
        configured stable-size interval across a process restart.  A source
        whose observable identity changed in between simply fails the
        fingerprint comparison and starts a fresh interval.
        """

        return cls(path, None, None, fingerprint, observed_at, observed_at)

    def matches(self, entry: StorageEntry, observed_value: str | None = None) -> bool:
        """Whether a fresh observation is the same unchanged occurrence.

        ``observed_value`` is the *computed* source fingerprint of the fresh
        entry.  When this observation carries real size/time facts they must be
        unchanged, and a previously verified digest must still match; a
        reconstructed durable observation (no size/time) compares by its
        persisted fingerprint alone, which already covers size and mtime.
        """

        if self.size is not None and (
            entry.size != self.size or entry.modified_at != self.modified_at
        ):
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
