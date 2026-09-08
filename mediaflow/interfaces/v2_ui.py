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
    as ``/ui-v2/dashboard`` work. Anything that looks like a file (a dotted
    final segment) or a traversal attempt is rejected so only built artifact
    bytes ever leave the process.
    """

    if ".." in PurePosixPath(path).parts:
        return None
    assets = v2_ui_assets()
    asset = assets.get(path)
    if asset is not None:
        return asset
    if PurePosixPath(path).suffix:
        return None
    return assets.get(V2_UI_PREFIX + "/")
