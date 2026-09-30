"""Read-only static serving boundary for the built V2 web artifact.

The V2 frontend is built by Node/Vite from ``web/`` (build-time tooling only).
The Python application serves the deterministic built artifact at the
documented ``/ui-v2/`` migration prefix without a Node production runtime.
This module never touches repositories, Storage, Providers, Tasks, Jobs or
execution services; it only reads files from the built artifact directory.

The artifact root resolves from the ``MEDIAFLOW_UI_V2_ASSET_ROOT`` environment
variable when set (deployment-owned, used by container packaging), otherwise
from the repository checkout's ``web/dist`` next to the ``mediaflow`` package.
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path, PurePosixPath

V2_UI_PREFIX = "/ui-v2"
ASSET_ROOT_ENV = "MEDIAFLOW_UI_V2_ASSET_ROOT"
_DEFAULT_ASSET_ROOT = Path(__file__).resolve().parents[2] / "web" / "dist"

_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".ico": "image/x-icon",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".webmanifest": "application/manifest+json",
    ".woff2": "font/woff2",
}

_INDEX_PATHS = (V2_UI_PREFIX, V2_UI_PREFIX + "/")

# The one built-SPA deep route whose operator identity is backend data, not a
# filename. The backend rules identifier contract
# (``RulesWorkspaceCommandService``) accepts bounded IDs containing ``.``,
# ``+``, ``@`` and internal spaces — including shapes such as ``proof.js``,
# ``proof.env`` or ``proof.type.bak`` that merely look like files. A refresh or
# direct entry of ``/ui-v2/rules/edit/<family>/<encoded-id>`` must therefore
# receive the entry document regardless of how the identity segment reads. The
# check below is anchored to that exact route shape: an allowlisted rules
# family and exactly one identity segment using the backend's bounded ASCII
# grammar. WSGI has already percent-decoded PATH_INFO, and traversal is refused
# before this runs. Every other dotted path outside this route stays an
# unknown asset that fails closed.
_RULES_EDIT_PREFIX = V2_UI_PREFIX + "/rules/edit/"
_RULES_EDIT_FAMILIES = frozenset(
    {
        "recognitionRules",
        "typeBindings",
        "recognitionTypes",
        "metadataPolicies",
        "namingPolicies",
        "classificationPolicies",
        "organizePolicies",
    }
)
_RULES_EDIT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@+ -]{0,63}")


def _rules_edit_segments(path: str) -> tuple[str, ...]:
    if not path.startswith(_RULES_EDIT_PREFIX):
        return ()
    return tuple(path[len(_RULES_EDIT_PREFIX) :].split("/"))


def _is_rules_edit_route(path: str) -> bool:
    """Whether the request path is exactly one supported rules edit route.

    A match never serves artifact bytes by itself: it only classifies the
    request as the SPA entry-document case, so the final segment is operator
    identity data rather than a filename. The identity check mirrors the
    backend rules command's bounded ASCII grammar, including file-like dotted
    IDs.
    """

    parts = _rules_edit_segments(path)
    if len(parts) != 2 or parts[0] not in _RULES_EDIT_FAMILIES:
        return False
    object_id = parts[1]
    return _RULES_EDIT_ID.fullmatch(object_id) is not None


def _is_rules_edit_route_shape(path: str) -> bool:
    """Identify an exact rules edit URL, including invalid family/ID values."""

    return len(_rules_edit_segments(path)) == 2


_cache_lock = threading.Lock()
_cache: dict[str, tuple[str, bytes]] | None = None


def asset_root() -> Path:
    configured = os.environ.get(ASSET_ROOT_ENV)
    if configured:
        return Path(configured).resolve()
    return _DEFAULT_ASSET_ROOT


def load_v2_assets(root: Path) -> dict[str, tuple[str, bytes]]:
    """Load one built V2 artifact as a request-path to (content type, body) map.

    Only allowlisted file types from the build output are served; unknown
    file types inside the artifact directory are never exposed. A missing or
    empty artifact yields an empty map so every V2 request fails closed.
    """

    index = root / "index.html"
    if not index.is_file():
        return {}
    assets: dict[str, tuple[str, bytes]] = {}
    for file in sorted(root.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        content_type = _CONTENT_TYPES.get(file.suffix.lower())
        if content_type is None:
            continue
        relative = file.relative_to(root).as_posix()
        assets[f"{V2_UI_PREFIX}/{relative}"] = (content_type, file.read_bytes())
    entry = assets.get(f"{V2_UI_PREFIX}/index.html")
    if entry is None:
        return {}
    for path in _INDEX_PATHS:
        assets[path] = entry
    return assets


def v2_ui_assets() -> dict[str, tuple[str, bytes]]:
    """Return the process-cached V2 artifact map, loading it on first use.

    Serving keeps the artifact loaded at first request so the boundary stays
    deterministic for the life of the process; rebuilds require a restart.
    """

    global _cache
    with _cache_lock:
        if _cache is None:
            _cache = load_v2_assets(asset_root())
        return _cache


def reset_v2_ui_cache() -> None:
    """Reload the artifact on the next request (deployment/test hook)."""

    global _cache
    with _cache_lock:
        _cache = None


def v2_ui_asset(path: str) -> tuple[str, bytes] | None:
    """Resolve one V2 UI request path; the caller has matched the prefix.

    Known built asset paths and the entry document are served. Unknown
    client-side routes fall back to the entry document so deep V2 routes such
    as ``/ui-v2/dashboard`` work. A dotted final segment is treated as an
    unknown asset and rejected so only built artifact bytes ever leave the
    process — except the one allowlisted rules edit route whose final segment
    is a backend object identity (dots included), never a filename. Traversal
    attempts are always rejected.
    """

    if ".." in PurePosixPath(path).parts:
        return None
    assets = v2_ui_assets()
    if _is_rules_edit_route_shape(path):
        if not _is_rules_edit_route(path):
            return None
        return assets.get(V2_UI_PREFIX + "/")
    asset = assets.get(path)
    if asset is not None:
        return asset
    # A dotted path is an unknown asset unless it is exactly one legal rules
    # edit route, whose identity segment is operator data published by the
    # backend, not a request for artifact files.
    if PurePosixPath(path).suffix and not _is_rules_edit_route(path):
        return None
    return assets.get(V2_UI_PREFIX + "/")
