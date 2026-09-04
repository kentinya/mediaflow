from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from mediaflow.application.read_only_storage import ReadOnlyStorageGuard
from mediaflow.domain.configuration_management import (
    ConfigurationVersionConflict,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
)
from mediaflow.domain.storage import (
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
    StoragePage,
)
from mediaflow.infrastructure.runtime_configuration import (
    create_storage_from_definition,
    load_storage_definition,
)

_MAX_PAGE_SIZE = 100
_DEFAULT_PAGE_SIZE = 50
_MAX_PATH_BYTES = 4096
_MAX_PATH_SEGMENTS = 128
_MAX_ENTRY_NAME_BYTES = 1024
_MAX_CURSOR_BYTES = 4096
_MAX_ADAPTER_CURSOR_BYTES = 2048
_CURSOR_TTL_SECONDS = 10 * 60
_CURSOR_VERSION = 1
_STORAGE_SECRET_ENV_FIELDS = {
    "openlist": ("tokenEnv",),
    "smb": ("usernameEnv", "passwordEnv"),
    "s3": ("accessKeyEnv", "secretKeyEnv", "sessionTokenEnv"),
    "r2": ("accessKeyEnv", "secretKeyEnv", "sessionTokenEnv"),
    "s3-compatible": ("accessKeyEnv", "secretKeyEnv", "sessionTokenEnv"),
}
_SAFE_STORAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class StorageBrowserError(RuntimeError):
    """A stable, secret-free failure from a bounded read-only Storage browser."""

    def __init__(
        self,
        code: str,
        category: str,
        message: str,
        *,
        status: int = 400,
        storage_id: str | None = None,
        path: str = "",
        retry_safe: bool = True,
        next_action: str,
        durable_state: str = "draft_and_prior_active_preserved",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.category = category
        self.message = message
        self.status = status
        self.storage_id = _safe_storage_id(storage_id)
        self.path = path if _is_safe_normalized_path(path) else ""
        self.retry_safe = retry_safe
        self.next_action = next_action
        self.durable_state = durable_state

    @property
    def details(self) -> dict[str, object]:
        return {
            "storageId": self.storage_id,
            "path": self.path,
            "stage": "storage_browser",
            "category": self.category,
            "durableState": self.durable_state,
            "sideEffects": "none",
            "retrySafe": self.retry_safe,
            "nextAction": self.next_action,
        }


class _CursorError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class StorageBrowserCursorCodec:
    """Encrypt and authenticate stateless cursors before they leave the API."""

    def __init__(
        self,
        secret: bytes | str | None = None,
        *,
        ttl_seconds: int = _CURSOR_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if isinstance(secret, str):
            secret = secret.encode("utf-8")
        if secret is None:
            secret = secrets.token_bytes(32)
        if not isinstance(secret, bytes) or not secret:
            raise ValueError("Storage browser cursor secret must be non-empty bytes")
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, int)
            or not 1 <= ttl_seconds
        ):
            raise ValueError("Storage browser cursor TTL must be positive")
        self._key = hashlib.sha256(secret).digest()
        self._ttl_seconds = ttl_seconds
        self._clock = clock

    def encode(self, context: Mapping[str, object], adapter_cursor: str) -> str:
        if not isinstance(adapter_cursor, str) or not adapter_cursor:
            raise _CursorError("missing_cursor")
        if len(adapter_cursor.encode("utf-8")) > _MAX_ADAPTER_CURSOR_BYTES:
            raise _CursorError("cursor_too_large")
        issued_at = int(self._clock())
        document = {
            "v": _CURSOR_VERSION,
            "issuedAt": issued_at,
            "expiresAt": issued_at + self._ttl_seconds,
            "context": dict(context),
            "adapterCursor": adapter_cursor,
        }
        try:
            plaintext = json.dumps(
                document, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise _CursorError("cursor_payload_invalid") from error
        nonce = secrets.token_bytes(16)
        ciphertext = self._xor(plaintext, nonce)
        tag = hmac.new(
            self._key,
            b"mediaflow-storage-cursor\0" + nonce + ciphertext,
            hashlib.sha256,
        )
        token = base64.urlsafe_b64encode(b"s" + nonce + tag.digest() + ciphertext).rstrip(b"=")
        if len(token) > _MAX_CURSOR_BYTES:
            raise _CursorError("cursor_too_large")
        return token.decode("ascii")

    def decode(self, token: str, context: Mapping[str, object]) -> str:
        if not isinstance(token, str) or not token or len(token) > _MAX_CURSOR_BYTES:
            raise _CursorError("malformed_cursor")
        if len(token) % 4 == 1:
            raise _CursorError("malformed_cursor")
        try:
            padded = token.encode("ascii") + b"=" * (-len(token) % 4)
            raw = base64.b64decode(padded, altchars=b"-_", validate=True)
        except (UnicodeEncodeError, ValueError) as error:
            raise _CursorError("malformed_cursor") from error
        if base64.urlsafe_b64encode(raw).rstrip(b"=") != token.encode("ascii"):
            raise _CursorError("malformed_cursor")
        if len(raw) < 1 + 16 + hashlib.sha256().digest_size or raw[:1] != b"s":
            raise _CursorError("malformed_cursor")
        nonce = raw[1:17]
        tag = raw[17 : 17 + hashlib.sha256().digest_size]
        ciphertext = raw[17 + hashlib.sha256().digest_size :]
        expected = hmac.new(
            self._key, b"mediaflow-storage-cursor\0" + nonce + ciphertext, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(tag, expected):
            raise _CursorError("tampered_cursor")
        try:
            document = json.loads(self._xor(ciphertext, nonce).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _CursorError("malformed_cursor") from error
        if not isinstance(document, dict):
            raise _CursorError("malformed_cursor")
        if document.get("v") != _CURSOR_VERSION:
            raise _CursorError("unsupported_cursor")
        issued_at = document.get("issuedAt")
        expires_at = document.get("expiresAt")
        if (
            isinstance(issued_at, bool)
            or not isinstance(issued_at, int)
            or isinstance(expires_at, bool)
            or not isinstance(expires_at, int)
            or expires_at < issued_at
        ):
            raise _CursorError("malformed_cursor")
        now = int(self._clock())
        if now < issued_at or now >= expires_at:
            raise _CursorError("expired_cursor")
        if document.get("context") != dict(context):
            raise _CursorError("context_mismatch")
        adapter_cursor = document.get("adapterCursor")
        if (
            not isinstance(adapter_cursor, str)
            or not adapter_cursor
            or len(adapter_cursor.encode("utf-8")) > _MAX_ADAPTER_CURSOR_BYTES
        ):
            raise _CursorError("malformed_cursor")
        return adapter_cursor

    def _xor(self, value: bytes, nonce: bytes) -> bytes:
        result = bytearray()
        block = 0
        while len(result) < len(value):
            result.extend(
                hmac.new(
                    self._key,
                    b"mediaflow-storage-cursor-keystream\0" + nonce + block.to_bytes(4, "big"),
                    hashlib.sha256,
                ).digest()
            )
            block += 1
        return bytes(left ^ right for left, right in zip(value, result, strict=False))


class StorageBrowserService:
    """Browse configured Storage roots without exposing adapters to transport code."""

    def __init__(
        self,
        managed,
        *,
        storage_adapters: Mapping[str, object] | None = None,
        cursor_secret: bytes | str | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._managed = managed
        self._storage_adapters = dict(storage_adapters or {})
        self._clock = clock
        self._cursor_codec = StorageBrowserCursorCodec(cursor_secret, clock=clock)

    def browse(
        self,
        revision_id: str,
        *,
        storage_id: str,
        path: str = "",
        limit: int = _DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
        expected_version: int | None = None,
        expected_digest: str | None = None,
    ) -> dict[str, object]:
        revision = self._require_revision(
            revision_id, expected_version=expected_version, expected_digest=expected_digest
        )
        return self.browse_revision(
            revision,
            storage_id=storage_id,
            path=path,
            limit=limit,
            cursor=cursor,
        )

    def browse_revision(
        self,
        revision: ManagedConfigurationRevision,
        *,
        storage_id: str,
        path: str = "",
        limit: int = _DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
        cursor_scope: str | None = None,
    ) -> dict[str, object]:
        """Browse one already-resolved revision without rereading configuration authority.

        Setup browsing resolves a Draft/Validated revision by ID in ``browse``.  Runtime
        browsing instead receives the immutable Active revision captured by the API binding;
        keeping this read path separate prevents a Draft or a second repository read from
        being substituted accidentally.
        """
        normalized_path = _normalize_storage_relative_path(path)
        normalized_limit = _validate_limit(limit)
        storage_value, definition = self._storage_definition(revision, storage_id)
        context = self._cursor_context(revision, storage_id, normalized_path, normalized_limit)
        if cursor_scope is not None:
            context["resourceLibraryId"] = cursor_scope
        adapter_cursor = None
        if cursor is not None:
            try:
                adapter_cursor = self._cursor_codec.decode(cursor, context)
            except _CursorError as error:
                raise self._cursor_failure(
                    error.reason, storage_id=storage_id, path=normalized_path
                ) from error
        guarded = self._open_storage(storage_value, definition, normalized_path)
        self._ensure_parent_directories(guarded, normalized_path, storage_id)
        try:
            page = guarded.list_page(normalized_path, limit=normalized_limit, cursor=adapter_cursor)
        except StorageError as error:
            raise self._storage_failure(error, storage_id, normalized_path) from error
        except Exception as error:
            raise self._storage_failure(error, storage_id, normalized_path) from error
        entries, next_adapter_cursor = self._page_entries(
            page, normalized_path, normalized_limit, storage_id
        )
        next_cursor = None
        if next_adapter_cursor is not None:
            try:
                next_cursor = self._cursor_codec.encode(context, next_adapter_cursor)
            except _CursorError as error:
                raise self._browser_failure(
                    "malformed_response", storage_id, normalized_path
                ) from error
        return self._document(
            revision,
            storage_value,
            definition.storage_type,
            normalized_path,
            normalized_limit,
            entries,
            next_cursor,
        )

    def validate_directory(
        self,
        revision_id: str,
        *,
        storage_id: str,
        path: str = "",
        expected_version: int | None = None,
        expected_digest: str | None = None,
    ) -> str:
        revision = self._require_revision(
            revision_id, expected_version=expected_version, expected_digest=expected_digest
        )
        normalized_path = _normalize_storage_relative_path(path)
        storage_value, definition = self._storage_definition(revision, storage_id)
        guarded = self._open_storage(storage_value, definition, normalized_path)
        self._ensure_parent_directories(guarded, normalized_path, storage_id)
        try:
            entry = guarded.stat(normalized_path)
        except StorageError as error:
            raise self._storage_failure(error, storage_id, normalized_path) from error
        except Exception as error:
            raise self._storage_failure(error, storage_id, normalized_path) from error
        if not isinstance(entry, StorageEntry):
            raise self._browser_failure("malformed_response", storage_id, normalized_path)
        if entry.entry_type is StorageEntryType.SYMLINK:
            raise self._browser_failure("symlink_not_selectable", storage_id, normalized_path)
        if entry.entry_type is not StorageEntryType.DIRECTORY:
            raise self._browser_failure("not_directory", storage_id, normalized_path)
        return normalized_path

    def _require_revision(
        self,
        revision_id: str,
        *,
        expected_version: int | None,
        expected_digest: str | None,
    ) -> ManagedConfigurationRevision:
        if (expected_version is None) != (expected_digest is None):
            raise ValueError("Storage browser expectedVersion and expectedDigest must be paired")
        revision = self._managed.require(revision_id)
        if revision.status not in {
            ManagedConfigurationStatus.DRAFT,
            ManagedConfigurationStatus.VALIDATED,
        }:
            raise ConfigurationVersionConflict(
                "Storage browser requires a Draft or Validated configuration revision",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
                durable_state="draft_and_prior_active_preserved",
                next_action="reload a Draft or Validated revision before browsing Storage",
            )
        if expected_version is not None and (
            revision.version != expected_version or revision.digest != expected_digest
        ):
            raise ConfigurationVersionConflict(
                "Storage browser requires the exact current revision; reload before browsing",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
                durable_state="draft_and_prior_active_preserved",
                next_action="reload the revision and retry the Storage browser",
            )
        return revision

    def _storage_definition(
        self, revision: ManagedConfigurationRevision, storage_id: str
    ) -> tuple[dict[str, object], Any]:
        if not isinstance(storage_id, str) or not _SAFE_STORAGE_ID.fullmatch(storage_id):
            raise self._browser_failure("storage_not_found", None, "")
        values = revision.document.get("storages", ())
        if not isinstance(values, list):
            raise self._browser_failure("invalid_configuration", storage_id, "")
        value = next(
            (item for item in values if isinstance(item, dict) and item.get("id") == storage_id),
            None,
        )
        if value is None:
            raise self._browser_failure("storage_not_found", storage_id, "")
        if value.get("enabled", True) is False:
            raise self._browser_failure("disabled", storage_id, "")
        try:
            definition = load_storage_definition(dict(value))
        except Exception as error:
            raise self._browser_failure("invalid_configuration", storage_id, "") from error
        if (
            definition.storage_type == "local"
            and os.path.normpath(definition.root_path) == os.path.sep
        ):
            raise self._browser_failure("invalid_configuration", storage_id, "")
        if self._missing_secrets(definition.storage_type, definition.options or {}):
            raise self._browser_failure("missing_secret", storage_id, "")
        return dict(value), definition

    def _open_storage(
        self,
        storage_value: Mapping[str, object],
        definition: Any,
        path: str,
    ) -> ReadOnlyStorageGuard:
        try:
            adapter = self._storage_adapters.get(definition.storage_id)
            if adapter is None:
                adapter = create_storage_from_definition(definition)
            if not _is_storage(adapter):
                raise TypeError("configured Storage adapter is invalid")
            if adapter.storage_id != definition.storage_id:
                raise TypeError("configured Storage adapter identity does not match the revision")
            return ReadOnlyStorageGuard(adapter)
        except StorageError as error:
            raise self._storage_failure(error, definition.storage_id, path) from error
        except Exception as error:
            raise self._browser_failure("connection_failed", definition.storage_id, path) from error

    def _ensure_parent_directories(
        self, storage: ReadOnlyStorageGuard, path: str, storage_id: str
    ) -> None:
        current = ""
        for segment in path.split("/") if path else ():
            current = f"{current}/{segment}" if current else segment
            try:
                entry = storage.stat(current)
            except StorageError as error:
                raise self._storage_failure(error, storage_id, path) from error
            except Exception as error:
                raise self._storage_failure(error, storage_id, path) from error
            if not isinstance(entry, StorageEntry):
                raise self._browser_failure("malformed_response", storage_id, path)
            if entry.entry_type is StorageEntryType.SYMLINK:
                raise self._browser_failure("symlink_not_traversable", storage_id, path)
            if entry.entry_type is not StorageEntryType.DIRECTORY:
                raise self._browser_failure("not_directory", storage_id, path)

    @staticmethod
    def _page_entries(
        page: object,
        path: str,
        limit: int,
        storage_id: str,
    ) -> tuple[tuple[StorageEntry, ...], str | None]:
        if isinstance(page, StoragePage):
            raw_entries = page.entries
            next_cursor = page.next_cursor
        elif isinstance(page, Sequence) and not isinstance(page, (str, bytes, bytearray)):
            raw_entries = page
            next_cursor = None
        else:
            raise StorageBrowserService._browser_failure("malformed_response", storage_id, path)
        if isinstance(raw_entries, (str, bytes, bytearray)) or not isinstance(
            raw_entries, Sequence
        ):
            raise StorageBrowserService._browser_failure("malformed_response", storage_id, path)
        if len(raw_entries) > limit:
            raise StorageBrowserService._browser_failure("malformed_response", storage_id, path)
        if next_cursor is not None and (
            not isinstance(next_cursor, str)
            or not next_cursor
            or len(next_cursor.encode("utf-8")) > _MAX_ADAPTER_CURSOR_BYTES
        ):
            raise StorageBrowserService._browser_failure("malformed_response", storage_id, path)
        values: list[StorageEntry] = []
        names: set[str] = set()
        for item in raw_entries:
            if not isinstance(item, StorageEntry):
                raise StorageBrowserService._browser_failure("malformed_response", storage_id, path)
            if not isinstance(item.name, str) or not item.name or item.name in {".", ".."}:
                raise StorageBrowserService._browser_failure("malformed_response", storage_id, path)
            if (
                "\x00" in item.name
                or "/" in item.name
                or "\\" in item.name
                or len(item.name.encode("utf-8")) > _MAX_ENTRY_NAME_BYTES
            ):
                raise StorageBrowserService._browser_failure("malformed_response", storage_id, path)
            expected_path = f"{path}/{item.name}" if path else item.name
            if item.path != expected_path or item.name in names:
                raise StorageBrowserService._browser_failure("malformed_response", storage_id, path)
            if not isinstance(item.entry_type, StorageEntryType):
                raise StorageBrowserService._browser_failure("malformed_response", storage_id, path)
            if (
                isinstance(item.size, bool)
                or not isinstance(item.size, int)
                or item.size < 0
                or item.size > 2**63 - 1
                or not isinstance(item.modified_at, datetime)
                or item.modified_at.tzinfo is None
            ):
                raise StorageBrowserService._browser_failure("malformed_response", storage_id, path)
            names.add(item.name)
            values.append(item)
        values.sort(key=lambda item: (item.name, item.path))
        if next_cursor is None and len(values) == limit:
            # A provider-neutral adapter that returns exactly a full page must
            # explicitly provide continuation; guessing would make exhaustion
            # indistinguishable from a provider truncation.
            pass
        return tuple(values), next_cursor

    def _document(
        self,
        revision: ManagedConfigurationRevision,
        storage_value: Mapping[str, object],
        storage_type: str,
        path: str,
        limit: int,
        entries: Sequence[StorageEntry],
        next_cursor: str | None,
    ) -> dict[str, object]:
        storage_id = str(storage_value.get("id"))
        breadcrumbs = [{"name": "Storage root", "path": "", "isRoot": True}]
        current = ""
        for segment in path.split("/") if path else ():
            current = f"{current}/{segment}" if current else segment
            breadcrumbs.append({"name": segment, "path": current, "isRoot": False})
        documents = []
        for entry in entries:
            is_symlink = entry.entry_type is StorageEntryType.SYMLINK
            is_directory = entry.entry_type is StorageEntryType.DIRECTORY
            documents.append(
                {
                    "name": entry.name,
                    "path": entry.path,
                    "type": entry.entry_type.value,
                    "entryType": entry.entry_type.value,
                    "size": entry.size,
                    "modifiedAt": entry.modified_at.astimezone(UTC).isoformat(),
                    "isDirectory": is_directory,
                    "isSymlink": is_symlink,
                    "traversable": is_directory,
                    "selectable": is_directory,
                }
            )
        exhausted = next_cursor is None
        return {
            "revision": revision.summary(),
            "revisionId": revision.revision_id,
            "revisionVersion": revision.version,
            "revisionDigest": revision.digest,
            "storage": {
                "id": storage_id,
                "name": str(storage_value.get("name") or storage_id),
                "type": storage_type,
                "readOnly": storage_value.get("readOnly", False) is True,
                "enabled": storage_value.get("enabled", True) is not False,
            },
            "storageId": storage_id,
            "storageName": str(storage_value.get("name") or storage_id),
            "storageType": storage_type,
            "pathScope": "storage_relative",
            "root": "",
            "rootPath": "",
            "canonicalPath": path,
            "path": path,
            "breadcrumbs": breadcrumbs,
            "entries": documents,
            "limit": limit,
            "nextCursor": next_cursor,
            "hasNext": next_cursor is not None,
            "exhausted": exhausted,
            "hasPrevious": False,
            "continuation": {
                "hasNext": next_cursor is not None,
                "exhausted": exhausted,
                "cursorBoundTo": "revision/storage/path/limit",
            },
            "sideEffects": "none",
            "retrySafe": True,
            "nextAction": (
                "open a directory, choose this directory, or use Next to load the next bounded page"
            ),
        }

    @staticmethod
    def _missing_secrets(storage_type: str, options: Mapping[str, object]) -> bool:
        for field in _STORAGE_SECRET_ENV_FIELDS.get(storage_type, ()):
            value = options.get(field)
            if value is not None and (
                not isinstance(value, str) or not value or not os.environ.get(value)
            ):
                return True
        return False

    @classmethod
    def _cursor_context(
        cls, revision: ManagedConfigurationRevision, storage_id: str, path: str, limit: int
    ) -> dict[str, object]:
        return {
            "revisionId": revision.revision_id,
            "revisionVersion": revision.version,
            "revisionDigest": revision.digest,
            "storageId": storage_id,
            "path": path,
            "limit": limit,
        }

    @classmethod
    def _storage_failure(
        cls, error: BaseException | None, storage_id: str, path: str
    ) -> StorageBrowserError:
        if isinstance(error, StorageError):
            code = error.code
        elif isinstance(error, FileNotFoundError):
            code = StorageErrorCode.NOT_FOUND
        elif isinstance(error, PermissionError):
            code = StorageErrorCode.PERMISSION_DENIED
        elif isinstance(error, TimeoutError):
            code = StorageErrorCode.TIMEOUT
        elif isinstance(error, ConnectionError):
            code = StorageErrorCode.CONNECTION_FAILED
        else:
            code = StorageErrorCode.UNKNOWN
        category = {
            StorageErrorCode.INVALID_PATH: "invalid_path",
            # A canonical browser path cannot contain parent traversal.  A
            # provider reporting traversal at this point therefore indicates
            # a symlink/root escape while resolving an already listed entry.
            StorageErrorCode.PATH_TRAVERSAL: "symlink_not_traversable",
            StorageErrorCode.NOT_FOUND: "not_found",
            StorageErrorCode.PERMISSION_DENIED: "permission_denied",
            StorageErrorCode.READ_ONLY: "permission_denied",
            StorageErrorCode.AUTHENTICATION_FAILED: "authentication_failed",
            StorageErrorCode.CONNECTION_FAILED: "connection_failed",
            StorageErrorCode.CONNECTION_LOST: "connection_failed",
            StorageErrorCode.TIMEOUT: "timeout",
            StorageErrorCode.RATE_LIMITED: "rate_limited",
            StorageErrorCode.UNSUPPORTED_OPERATION: "unsupported_operation",
            StorageErrorCode.IO_ERROR: "connection_failed",
        }.get(code, "unknown")
        return cls._browser_failure(category, storage_id, path)

    @classmethod
    def _cursor_failure(cls, reason: str, *, storage_id: str, path: str) -> StorageBrowserError:
        category = "cursor_expired" if reason == "expired_cursor" else "cursor_invalid"
        return cls._browser_failure(category, storage_id, path)

    @classmethod
    def _browser_failure(
        cls, category: str, storage_id: str | None, path: str
    ) -> StorageBrowserError:
        messages = {
            "storage_not_found": (
                "configured Storage was not found",
                404,
                "reload the configuration revision and choose one configured Storage",
            ),
            "disabled": (
                "the selected Storage is disabled in the current configuration",
                409,
                "enable the Storage in the current configuration, validate it, then retry browsing",
            ),
            "invalid_configuration": (
                "Storage configuration is invalid before a provider read could start",
                400,
                "correct the bounded Storage fields, reload the configuration, and retry",
            ),
            "missing_secret": (
                "a required deployment-owned Storage credential is unavailable",
                503,
                "set the referenced environment variable outside MediaFlow, reload, and retry",
            ),
            "invalid_path": (
                "Storage-relative path is invalid",
                400,
                "use the displayed Storage-relative breadcrumb or enter a safe relative path",
            ),
            "not_found": (
                "Storage directory was not found",
                404,
                "make the configured directory available, reload, and retry",
            ),
            "not_directory": (
                "the selected Storage path is not a directory",
                400,
                "choose a directory entry or return to its parent directory",
            ),
            "symlink_not_traversable": (
                "symbolic-link paths cannot be traversed by the Storage browser",
                400,
                "choose a real directory inside the configured Storage root",
            ),
            "symlink_not_selectable": (
                "symbolic-link paths cannot be selected as library roots",
                400,
                "choose a real directory inside the configured Storage root",
            ),
            "permission_denied": (
                "Storage read permission was denied",
                403,
                "grant MediaFlow read/list permission, reload, and retry",
            ),
            "authentication_failed": (
                "Storage authentication failed",
                503,
                "correct the deployment-owned credential reference or access policy, reload, "
                "and retry",
            ),
            "connection_failed": (
                "Storage could not be reached",
                503,
                "check the endpoint, network and service availability, reload, and retry",
            ),
            "timeout": (
                "Storage read exceeded its bounded deadline",
                503,
                "check Storage availability and timeout settings, reload, and retry",
            ),
            "rate_limited": (
                "Storage rate-limited the directory read",
                503,
                "wait for the provider limit to clear, then reload and retry",
            ),
            "cursor_invalid": (
                "Storage browser continuation is invalid or no longer matches this revision",
                400,
                "reload the current revision and restart browsing from the directory root",
            ),
            "cursor_expired": (
                "Storage browser continuation has expired",
                400,
                "reload the current revision and restart browsing from the directory root",
            ),
            "malformed_response": (
                "Storage returned an invalid bounded directory response",
                503,
                "inspect the Storage adapter response, then reload and retry",
            ),
            "unknown": (
                "Storage browser failed with an unclassified provider response",
                503,
                "inspect bounded Storage configuration and service health, then reload and retry",
            ),
            "resource_library_not_found": (
                "the requested ResourceLibrary is not available in the Active runtime",
                404,
                "reload the current Active runtime and choose an enabled ResourceLibrary",
            ),
            "resource_library_mismatch": (
                "the requested ResourceLibrary does not use this Storage",
                400,
                "choose a ResourceLibrary bound to the selected configured Storage",
            ),
        }
        message, status, next_action = messages.get(category, messages["unknown"])
        return StorageBrowserError(
            f"storage_browser_{category}",
            category,
            message,
            status=status,
            storage_id=storage_id,
            path=path,
            next_action=next_action,
        )


class RuntimeFilesBrowserService:
    """Read the configured Storage surface from one immutable Active runtime snapshot."""

    MAX_MEMBERSHIP_LIBRARIES = 32

    def __init__(
        self,
        managed,
        *,
        active_revision: ManagedConfigurationRevision,
        runtime_configuration,
        file_index=None,
        storage_adapters: Mapping[str, object] | None = None,
        cursor_secret: bytes | str | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if active_revision.status is not ManagedConfigurationStatus.ACTIVE:
            raise ValueError("runtime Files browsing requires an Active configuration revision")
        if (
            getattr(runtime_configuration, "configuration_snapshot_id", None)
            != active_revision.revision_id
            or getattr(runtime_configuration, "configuration_snapshot_digest", None)
            != active_revision.digest
        ):
            raise ValueError("runtime Files browser snapshot does not match the Active revision")
        self._revision = active_revision
        self._runtime_configuration = runtime_configuration
        self._file_index = file_index
        self._browser = StorageBrowserService(
            managed,
            storage_adapters=storage_adapters,
            cursor_secret=cursor_secret,
            clock=clock,
        )
        self._libraries = tuple(
            sorted(
                (
                    library
                    for library in getattr(runtime_configuration, "resource_libraries", ())
                    if getattr(library, "enabled", True) is True
                ),
                key=lambda library: library.library_id,
            )
        )

    def browse(
        self,
        *,
        storage_id: str,
        path: str = "",
        limit: int = _DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
        resource_library_id: str | None = None,
    ) -> dict[str, object]:
        try:
            normalized_path = _normalize_storage_relative_path(path)
        except StorageBrowserError as error:
            raise self._runtime_error(error) from error
        libraries = self._libraries_for(storage_id, resource_library_id)
        try:
            document = self._browser.browse_revision(
                self._revision,
                storage_id=storage_id,
                path=normalized_path,
                limit=limit,
                cursor=cursor,
                cursor_scope=resource_library_id,
            )
        except StorageBrowserError as error:
            raise self._runtime_error(error) from error

        entries = []
        for raw_entry in document["entries"]:
            entry = dict(raw_entry)
            entry["indexMembership"] = self._membership(
                entry["path"], libraries, is_file=entry["type"] == StorageEntryType.FILE.value
            )
            entries.append(entry)
        document["entries"] = entries
        document["surface"] = "files"
        document["surfaceLabel"] = "Files"
        document["fileIndexSurface"] = "/api/v1/file-index"
        document["configuration"] = {
            "authority": "MANAGED",
            "revisionId": self._revision.revision_id,
            "version": self._revision.version,
            "digest": self._revision.digest,
        }
        document["nextAction"] = (
            "open a directory, inspect FileIndex membership, or use Next to load the next "
            "bounded page"
        )
        return document

    def _libraries_for(
        self, storage_id: str, resource_library_id: str | None
    ) -> tuple[object, ...]:
        if resource_library_id is None:
            return tuple(library for library in self._libraries if library.storage_id == storage_id)
        library = next(
            (item for item in self._libraries if item.library_id == resource_library_id),
            None,
        )
        if library is None:
            raise self._runtime_error(
                StorageBrowserService._browser_failure("resource_library_not_found", None, "")
            )
        if library.storage_id != storage_id:
            raise self._runtime_error(
                StorageBrowserService._browser_failure("resource_library_mismatch", storage_id, "")
            )
        return (library,)

    def _membership(
        self,
        path: str,
        libraries: tuple[object, ...],
        *,
        is_file: bool,
    ) -> dict[str, object]:
        if not is_file:
            return {
                "available": True,
                "indexed": False,
                "memberships": [],
                "total": 0,
                "truncated": False,
                "nextAction": "FileIndex membership applies to file entries",
            }
        if not libraries:
            return {
                "available": False,
                "indexed": False,
                "memberships": [],
                "total": 0,
                "truncated": False,
                "nextAction": "configure an enabled ResourceLibrary for this Storage",
            }
        if self._file_index is None:
            return {
                "available": False,
                "indexed": False,
                "memberships": [],
                "total": 0,
                "truncated": False,
                "nextAction": "reload after the runtime FileIndex repository is available",
            }
        find = getattr(self._file_index, "find_by_path", None)
        if not callable(find):
            return {
                "available": False,
                "indexed": False,
                "memberships": [],
                "total": 0,
                "truncated": False,
                "nextAction": "inspect the FileIndex repository and reload Files",
            }
        bounded_libraries = libraries[: self.MAX_MEMBERSHIP_LIBRARIES]
        memberships: list[dict[str, object]] = []
        try:
            for library in bounded_libraries:
                if not _path_in_resource_library(path, library.root_path):
                    continue
                record = find(library.storage_id, library.library_id, path)
                if record is None:
                    continue
                memberships.append(
                    {
                        "fileId": record.file_id,
                        "resourceLibraryId": record.resource_library_id,
                        "path": record.path,
                        "scanStatus": record.scan_status.value,
                        "change": record.change.value,
                        "size": record.size,
                        "modifiedAt": record.modified_at.isoformat(),
                        "updatedAt": record.updated_at.isoformat(),
                    }
                )
        except Exception:
            return {
                "available": False,
                "indexed": False,
                "memberships": [],
                "total": 0,
                "truncated": False,
                "nextAction": "inspect the FileIndex repository and reload Files",
            }
        return {
            "available": True,
            "indexed": bool(memberships),
            "memberships": memberships,
            "total": len(memberships),
            "truncated": len(libraries) > len(bounded_libraries),
            "libraryScope": "requested" if len(libraries) == 1 else "all_enabled",
            "nextAction": (
                "open FileIndex for indexed discovery state"
                if memberships
                else "run a bounded ResourceLibrary scan to add this file to FileIndex"
            ),
        }

    @staticmethod
    def _runtime_error(error: StorageBrowserError) -> StorageBrowserError:
        error.durable_state = "active_runtime_preserved"
        return error


def _validate_limit(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= _MAX_PAGE_SIZE:
        raise ValueError("Storage browser limit must be between 1 and 100")
    return value


def _normalize_storage_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        if value == "":
            return ""
        raise StorageBrowserService._browser_failure("invalid_path", None, "")
    if len(value.encode("utf-8")) > _MAX_PATH_BYTES:
        raise StorageBrowserService._browser_failure("invalid_path", None, "")
    if (
        value.startswith(("/", "\\"))
        or "\\" in value
        or urlparse(value).scheme
        or (len(value) > 1 and value[1] == ":")
    ):
        raise StorageBrowserService._browser_failure("invalid_path", None, "")
    segments = value.split("/")
    if len(segments) > _MAX_PATH_SEGMENTS or any(
        not segment or segment in {".", ".."} for segment in segments
    ):
        raise StorageBrowserService._browser_failure("invalid_path", None, "")
    return "/".join(segments)


def _is_safe_normalized_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return value == ""
    try:
        return _normalize_storage_relative_path(value) == value
    except StorageBrowserError:
        return False


def _path_in_resource_library(path: str, root: str) -> bool:
    if not root:
        return True
    return path == root or path.startswith(root + "/")


def _safe_storage_id(value: object) -> str:
    return value if isinstance(value, str) and _SAFE_STORAGE_ID.fullmatch(value) else "unknown"


def _is_storage(value: object) -> bool:
    return all(
        hasattr(value, attribute)
        for attribute in ("storage_id", "name", "read_only", "capabilities", "list", "stat")
    )


normalize_storage_relative_path = _normalize_storage_relative_path
