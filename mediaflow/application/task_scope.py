"""Resolve one paused Task's exact ResourceLibrary scope from its pinned runtime.

Both the remaining-scope exact-Preview recovery boundary and the durable
remaining-scope recovery preparation must resolve the Task's durable
``scope_path`` against the *pinned* runtime's ResourceLibrary roots exactly the
same way, so the reviewed/observed scope can never diverge between the two.
This module owns that one pure resolution and nothing else: it reads the runtime
projection and one scope string, never Storage, a Provider, a Task or a
repository.
"""

from __future__ import annotations

from pathlib import PurePath


class ScopeResolutionError(ValueError):
    """A bounded, operator-correctable scope-resolution refusal.

    ``reason`` is a closed code the callers map onto their own error envelope;
    ``message`` is a secret-free explanation.  It never contains a host path.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def _runtime_library(runtime, resource_library_id: str):
    matches = tuple(
        value
        for value in getattr(runtime, "resource_libraries", ())
        if getattr(value, "library_id", None) == resource_library_id
    )
    if len(matches) != 1 or not getattr(matches[0], "enabled", False):
        raise ScopeResolutionError(
            "resource_library_not_found",
            "the selected ResourceLibrary is unavailable in the pinned configuration",
        )
    return matches[0]


def resolve_resource_library_scope(runtime, scope_path):
    """Resolve one durable ``scope_path`` to ``(library, relative_scope)``.

    A scope that cannot be proven to belong to exactly one enabled
    ResourceLibrary in the pinned runtime is refused: the recovery boundary must
    never widen an unresolvable scope into a whole-library review, because that
    would observe/review (and could later execute) work the original run never
    admitted.
    """

    scope = scope_path
    if scope is None or not str(scope).strip():
        enabled = tuple(
            value
            for value in getattr(runtime, "resource_libraries", ())
            if getattr(value, "enabled", False)
        )
        if len(enabled) != 1:
            raise ScopeResolutionError(
                "scope_unresolved",
                "this run's admitted scope does not resolve to exactly one ResourceLibrary, "
                "so its exact remaining scope cannot be reproduced",
            )
        return _runtime_library(runtime, enabled[0].library_id), ""
    raw = str(scope).replace("\\", "/").strip()
    candidate = PurePath(raw)
    matches: list[tuple[int, str, str]] = []
    for library_id, display_root in tuple(getattr(runtime, "resource_display_roots", ()) or ()):
        root = PurePath(str(display_root).replace("\\", "/").rstrip("/") or "/")
        if candidate == root or root in candidate.parents:
            matches.append((len(root.parts), library_id, candidate.relative_to(root).as_posix()))
    relative_candidate = candidate
    if raw.startswith("/"):
        relative_candidate = None
    for value in getattr(runtime, "resource_libraries", ()):
        if not getattr(value, "enabled", False):
            continue
        if relative_candidate is None:
            continue
        root_path = str(getattr(value, "root_path", "") or "").replace("\\", "/").strip("/")
        if not root_path:
            matches.append((0, value.library_id, relative_candidate.as_posix()))
            continue
        root = PurePath(root_path)
        if relative_candidate == root or root in relative_candidate.parents:
            matches.append(
                (
                    len(root.parts),
                    value.library_id,
                    relative_candidate.relative_to(root).as_posix(),
                )
            )
    if not matches:
        raise ScopeResolutionError(
            "scope_unresolved",
            "this run's admitted scope does not resolve to a ResourceLibrary in its own "
            "pinned configuration, so its exact remaining scope cannot be reproduced",
        )
    best_depth = max(match[0] for match in matches)
    winners = [match for match in matches if match[0] == best_depth]
    if len({match[1] for match in winners}) != 1:
        raise ScopeResolutionError(
            "scope_unresolved",
            "this run's admitted scope is claimed by more than one ResourceLibrary in its "
            "own pinned configuration, so its exact remaining scope is ambiguous",
        )
    _, library_id, relative = winners[0]
    library = _runtime_library(runtime, library_id)
    relative = "" if relative == "." else relative
    return library, _normalize_library_relative_path(relative, allow_empty=True)


def _normalize_library_relative_path(value: object, *, allow_empty: bool) -> str:
    if value == "" and allow_empty:
        return ""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ScopeResolutionError(
            "invalid_path", "relativePath must be a safe ResourceLibrary-relative path"
        )
    if value.startswith(("/", "\\")) or "\\" in value or ":" in value:
        raise ScopeResolutionError(
            "invalid_path", "relativePath must be a safe ResourceLibrary-relative path"
        )
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ScopeResolutionError(
            "invalid_path", "relativePath must not escape the ResourceLibrary"
        )
    return "/".join(parts)


__all__ = [
    "ScopeResolutionError",
    "resolve_resource_library_scope",
]
