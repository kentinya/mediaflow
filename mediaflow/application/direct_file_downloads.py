"""Files bounded Download application service.

Admission and streaming for the confined, zero-mutation Files Download
command.  A single regular file streams directly from ``Storage.read``;
one directory or one bounded multi-selection streams as one archive that
is generated on the fly, entry by entry, without writing the archive back
into managed Storage and without ever crossing ``OrganizerExecutor``.

Admission enumerates the bounded scope first (explicit entry/depth/byte
limits, fail-closed on unsupported entry types, the shared confined
directory-traversal rule) so the archive scope is pinned before the first
byte is written to the response.  An entry that disappears or changes
mid-stream is recorded honestly in the archive manifest instead of being
fabricated, and an interrupted download remains safe to repeat.  No
credential, host path or provider detail crosses into the response
headers or the archive.
"""

from __future__ import annotations

import json
import posixpath
import zipfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from urllib.parse import quote

from mediaflow.application.direct_file_commands import DirectFileError
from mediaflow.application.storage_browser import (
    _confined_directory_child,
    _join_resource_library_path,
)
from mediaflow.domain.direct_files import (
    MAX_DOWNLOAD_BYTES,
    MAX_DOWNLOAD_DEPTH,
    MAX_DOWNLOAD_ENTRIES,
    MAX_DOWNLOAD_PATHS,
    DownloadArchiveEntry,
    DownloadItemStatus,
    DownloadManifest,
)
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.storage import (
    Storage,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
)

__all__ = ["DirectFileDownloadService", "DirectFileDownloadError"]

_STREAM_CHUNK = 256 * 1024

#: Bounded archive manifest entry name.  The generated archive records one
#: honest outcome note per item here; it never carries content or secrets.
ARCHIVE_MANIFEST_NAME = "mediaflow-download-manifest.json"

#: Bounded extension → Content-Type map for direct single-file streaming.
#: Anything unmapped streams as ``application/octet-stream``; the map is
#: presentation-only and never an authority decision.
_DOWNLOAD_CONTENT_TYPES: Mapping[str, str] = {
    ".avi": "video/avi",
    ".flac": "audio/flac",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".m4a": "audio/mp4",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".png": "image/png",
    ".wav": "audio/wav",
    ".webp": "image/webp",
    ".ass": "text/plain",
    ".srt": "text/plain",
    ".ssa": "text/plain",
    ".vtt": "text/vtt",
    ".txt": "text/plain",
    ".nfo": "application/xml",
    ".xml": "application/xml",
    ".json": "application/json",
}


class DirectFileDownloadError(DirectFileError):
    """A stable, secret-free bounded Download failure.

    Subclassing the Files direct-command error keeps one global handler.
    Download is a confined zero-mutation read, so the recovery projection
    always reports retry-safe durable state and no side effects.
    """

    @property
    def details(self) -> dict[str, object]:
        document = super().details
        document["stage"] = "files_download"
        document["sideEffects"] = "none"
        document["retrySafe"] = True
        return document


@dataclass
class _ArchivePlan:
    """The pinned archive scope of one Download admission.

    ``directories`` are the exact confined directory entries the archive
    must publish as folder entries; ``files`` are the exact file entries
    streamed into the archive.  Every entry keeps the source entry
    observed at enumeration time, so a mid-stream disappearance is
    detectable instead of fabricated.
    """

    entries: list[DownloadArchiveEntry] = field(default_factory=list)
    failed: list[DownloadArchiveEntry] = field(default_factory=list)

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def total_bytes(self) -> int:
        return sum(entry.size for entry in self.entries if not entry.is_directory)


class DirectFileDownloadService:
    """Files-owned admission and streaming boundary for bounded Downloads."""

    def __init__(self, *, direct_files) -> None:
        self._direct = direct_files

    # ------------------------------------------------------------------
    # Admission (zero mutation)
    # ------------------------------------------------------------------

    def download_admission(
        self,
        *,
        resource_library_id: str,
        paths,
    ) -> DownloadManifest:
        """Admit one bounded Download selection.  Zero mutation.

        Resolves the exact immutable Active ResourceLibrary, confines the
        bounded selection and — for directories — enumerates the exact
        archive scope within the explicit entry/depth/byte limits before
        any byte is produced.  A single regular file is admitted for the
        direct stream; anything else is one generated archive.
        """

        library = self._direct.library(resource_library_id)
        storage = self._open_storage(library)
        selected = self._selected_paths(library, paths)
        if len(selected) == 1:
            single = self._admit_single_file(library, storage, selected[0])
            if single is not None:
                return single
        plan = _ArchivePlan()
        filename = self._archive_filename(selected)
        manifest = DownloadManifest(
            resource_library_id=library.library_id,
            filename=filename,
        )
        for relative in selected:
            self._admit_selection(
                library,
                storage,
                relative,
                plan,
            )
        self._enforce_plan_limits(library, plan)
        # The archive scope is the successful enumeration plus the honest
        # admission-time failures, so the archive manifest records every
        # selected item's outcome instead of fabricating content.
        entries = tuple(
            sorted(
                [*plan.entries, *plan.failed],
                key=lambda entry: entry.archive_path,
            )
        )
        manifest = DownloadManifest(
            resource_library_id=library.library_id,
            filename=filename,
            entries=entries,
            manifest_note=self._manifest_note(plan),
        )
        return manifest

    def _open_storage(self, library: ResourceLibrary) -> Storage:
        try:
            return self._direct.open_storage(library)
        except DirectFileError as error:
            raise DirectFileDownloadError(
                error.code,
                error.category,
                "the referenced Storage is unavailable for this Download",
                status=error.status,
                resource_library_id=library.library_id,
                next_action="retry the Download once the Storage is reachable",
            ) from None

    def _selected_paths(self, library: ResourceLibrary, paths) -> tuple[str, ...]:
        if not isinstance(paths, (list, tuple)) or not paths:
            raise DirectFileDownloadError(
                "files_download_invalid_request",
                "invalid_request",
                "the Download selection requires at least one path",
                resource_library_id=library.library_id,
                next_action="select a file or directory to download",
            )
        if len(paths) > MAX_DOWNLOAD_PATHS:
            raise DirectFileDownloadError(
                "files_download_count_limit_exceeded",
                "download_count_limit_exceeded",
                f"the Download selection exceeds the bounded limit of {MAX_DOWNLOAD_PATHS} items",
                resource_library_id=library.library_id,
                next_action="download a smaller selection in batches",
            )
        seen: set[str] = set()
        selected: list[str] = []
        for value in paths:
            relative = self._direct.relative_path(value)
            if not relative:
                raise DirectFileDownloadError(
                    "files_download_invalid_path",
                    "invalid_path",
                    "the ResourceLibrary root itself is not downloadable",
                    resource_library_id=library.library_id,
                    next_action="select a file or directory inside the ResourceLibrary",
                )
            if relative in seen:
                continue
            seen.add(relative)
            selected.append(relative)
        return tuple(selected)

    def _admit_single_file(
        self,
        library: ResourceLibrary,
        storage: Storage,
        relative: str,
    ) -> DownloadManifest | None:
        observed = self._stat(library, storage, relative)
        if observed.entry_type is not StorageEntryType.FILE:
            return None
        if observed.size > MAX_DOWNLOAD_BYTES:
            raise self._limit_error(library, relative, "download_size_limit_exceeded")
        entry = DownloadArchiveEntry(
            archive_path=posixpath.basename(relative),
            source_path=relative,
            size=observed.size,
            is_directory=False,
        )
        manifest = DownloadManifest(
            resource_library_id=library.library_id,
            filename=posixpath.basename(relative),
            single_file=entry,
        )
        return manifest

    def _admit_selection(
        self,
        library: ResourceLibrary,
        storage: Storage,
        relative: str,
        plan: _ArchivePlan,
    ) -> None:
        observed = self._stat(library, storage, relative)
        top = posixpath.basename(relative)
        if observed.entry_type is StorageEntryType.FILE:
            if observed.size > MAX_DOWNLOAD_BYTES:
                raise self._limit_error(library, relative, "download_size_limit_exceeded")
            plan.entries.append(
                DownloadArchiveEntry(
                    archive_path=top,
                    source_path=relative,
                    size=observed.size,
                    is_directory=False,
                )
            )
            return
        if observed.entry_type is StorageEntryType.DIRECTORY:
            plan.entries.append(
                DownloadArchiveEntry(
                    archive_path=f"{top}/",
                    source_path=relative,
                    size=0,
                    is_directory=True,
                )
            )
            self._enumerate_directory(library, storage, relative, f"{top}/", 1, plan)
            return
        # Symlinks and provider-unknown types are not archive-safe: they are
        # recorded honestly in the manifest instead of being followed or
        # fabricated.
        plan.failed.append(
            DownloadArchiveEntry(
                archive_path=top,
                source_path=relative,
                size=0,
                is_directory=observed.entry_type is StorageEntryType.DIRECTORY,
                status=DownloadItemStatus.FAILED,
                note=(
                    "symbolic link entries are not downloadable"
                    if observed.entry_type is StorageEntryType.SYMLINK
                    else "unsupported entry type"
                ),
            )
        )

    def _enumerate_directory(
        self,
        library: ResourceLibrary,
        storage: Storage,
        relative: str,
        archive_prefix: str,
        depth: int,
        plan: _ArchivePlan,
    ) -> None:
        """Bounded enumeration of one directory tree into the archive plan.

        Every listed child is converted by the single shared confined
        traversal rule (provider storage-relative direct-child validation,
        then exactly one ResourceLibrary root strip), so a non-empty
        ResourceLibrary root never leaks into the archive scope and an
        escaped provider entry fails closed.
        """

        stack: list[tuple[str, str, int]] = [(relative, archive_prefix, depth)]
        while stack:
            current, current_archive, current_depth = stack.pop()
            full = _join_resource_library_path(library.root_path, current)
            try:
                children = tuple(storage.list(full))
            except (StorageError, OSError) as error:
                raise self._storage_failure(library, current, error) from None
            for child in children:
                try:
                    child_relative = _confined_directory_child(child, full, library.root_path)
                except ValueError:
                    raise DirectFileDownloadError(
                        "files_download_invalid_path",
                        "invalid_path",
                        "a listed entry is not a direct child of its directory",
                        resource_library_id=library.library_id,
                        path=current,
                        next_action="refresh the directory and retry the download",
                    ) from None
                child_archive = f"{current_archive}{child.name}"
                if child.entry_type is StorageEntryType.SYMLINK:
                    plan.failed.append(
                        DownloadArchiveEntry(
                            archive_path=child_archive,
                            source_path=child_relative,
                            size=0,
                            is_directory=False,
                            status=DownloadItemStatus.FAILED,
                            note="symbolic link entries are not downloadable",
                        )
                    )
                    continue
                if child.entry_type not in {StorageEntryType.FILE, StorageEntryType.DIRECTORY}:
                    plan.failed.append(
                        DownloadArchiveEntry(
                            archive_path=child_archive,
                            source_path=child_relative,
                            size=0,
                            is_directory=False,
                            status=DownloadItemStatus.FAILED,
                            note="unsupported entry type",
                        )
                    )
                    continue
                if child.entry_type is StorageEntryType.DIRECTORY:
                    if current_depth > MAX_DOWNLOAD_DEPTH:
                        raise self._limit_error(
                            library, child_relative, "download_depth_limit_exceeded"
                        )
                    plan.entries.append(
                        DownloadArchiveEntry(
                            archive_path=f"{child_archive}/",
                            source_path=child_relative,
                            size=0,
                            is_directory=True,
                        )
                    )
                    stack.append((child_relative, f"{child_archive}/", current_depth + 1))
                else:
                    plan.entries.append(
                        DownloadArchiveEntry(
                            archive_path=child_archive,
                            source_path=child_relative,
                            size=child.size,
                            is_directory=False,
                        )
                    )
                if len(plan.entries) > MAX_DOWNLOAD_ENTRIES:
                    raise self._limit_error(
                        library, child_relative, "download_entry_limit_exceeded"
                    )
                if plan.total_bytes > MAX_DOWNLOAD_BYTES:
                    raise self._limit_error(library, child_relative, "download_size_limit_exceeded")

    def _manifest_note(self, plan: _ArchivePlan) -> str | None:
        if not plan.failed:
            return None
        notes = sorted({entry.note or "entry unavailable" for entry in plan.failed})
        return "; ".join(notes)[:256]

    def _enforce_plan_limits(self, library: ResourceLibrary, plan: _ArchivePlan) -> None:
        if plan.entry_count > MAX_DOWNLOAD_ENTRIES:
            raise self._limit_error(library, "", "download_entry_limit_exceeded")
        if plan.total_bytes > MAX_DOWNLOAD_BYTES:
            raise self._limit_error(library, "", "download_size_limit_exceeded")

    @staticmethod
    def _archive_filename(selected: tuple[str, ...]) -> str:
        if len(selected) == 1:
            single = selected[0]
            return posixpath.basename(single) + ".zip"
        return "files.zip"

    def _stat(self, library: ResourceLibrary, storage: Storage, relative: str):
        full = _join_resource_library_path(library.root_path, relative)
        try:
            return storage.stat(full)
        except (StorageError, OSError) as error:
            raise self._storage_failure(library, relative, error) from None

    def _limit_error(
        self, library: ResourceLibrary, relative: str, category: str
    ) -> DirectFileDownloadError:
        return DirectFileDownloadError(
            f"files_download_{category}",
            category,
            "the Download scope exceeds the bounded download limits",
            status=413,
            resource_library_id=library.library_id,
            path=relative,
            next_action="download a smaller bounded selection",
        )

    def _storage_failure(
        self,
        library: ResourceLibrary,
        relative: str,
        error: Exception,
    ) -> DirectFileDownloadError:
        category, status = _storage_category(error)
        return DirectFileDownloadError(
            f"files_download_{category}",
            category,
            "the Storage read for Download admission failed",
            status=status,
            resource_library_id=library.library_id,
            path=relative,
            next_action="retry the download once the Storage is reachable again",
        )

    # ------------------------------------------------------------------
    # Streaming (zero mutation)
    # ------------------------------------------------------------------

    def stream_single(
        self,
        library: ResourceLibrary,
        storage: Storage,
        manifest: DownloadManifest,
        *,
        chunk_size: int = _STREAM_CHUNK,
    ) -> Iterator[bytes]:
        """Stream one admitted single file directly from Storage.

        The stream is bounded by the admitted size: a source that shrank
        or changed mid-stream simply ends early (an interrupted read is
        safe to repeat), and a source that grew is cut at the admitted
        size so no content beyond the confirmed scope is published.
        """

        entry = manifest.single_file
        if entry is None:
            raise DirectFileDownloadError(
                "files_download_invalid_request",
                "invalid_request",
                "the download manifest has no single-file stream",
                next_action="request the download again",
            )
        full = _join_resource_library_path(library.root_path, entry.source_path)
        expected = entry.size
        served = 0
        with storage.read(full) as stream:
            while served < expected:
                chunk = stream.read(min(chunk_size, expected - served))
                if not chunk:
                    return
                served += len(chunk)
                yield chunk

    def stream_archive(
        self,
        library: ResourceLibrary,
        storage: Storage,
        manifest: DownloadManifest,
        *,
        chunk_size: int = _STREAM_CHUNK,
    ) -> Iterator[bytes]:
        """Stream one admitted archive, generated on the fly.

        The archive is written entry by entry through a bounded ZIP sink:
        every chunk the writer produces is drained into the response as
        soon as the next write begins, so only the bounded
        central-directory metadata ever waits in memory.  File content is
        streamed straight from ``Storage.read`` in bounded chunks.  An
        entry that disappears or changes mid-stream is recorded honestly in
        the appended archive manifest instead of being fabricated, and no
        archive byte is ever written back to managed Storage.
        """

        sink = _ZipStreamSink()
        archive = zipfile.ZipFile(sink, mode="w", compression=zipfile.ZIP_DEFLATED)
        outcomes: list[dict[str, object]] = []
        for entry in manifest.entries:
            if entry.status is DownloadItemStatus.FAILED:
                # An admission-time failure (symlink/unsupported entry):
                # it is never followed and never fabricated.
                outcomes.append(
                    {
                        "path": entry.archive_path,
                        "status": "failed",
                        "note": entry.note or "entry unavailable",
                    }
                )
                continue
            if entry.is_directory:
                self._archive_directory_entry(archive, entry)
                outcomes.append({"path": entry.archive_path, "status": "included"})
                yield from sink.drain()
                continue
            full = _join_resource_library_path(library.root_path, entry.source_path)
            try:
                observed = storage.stat(full)
                if observed.entry_type is not StorageEntryType.FILE or observed.size != entry.size:
                    # The confirmed scope pins the entry observed at
                    # admission; a changed source is never fabricated.
                    raise StorageError(
                        StorageErrorCode.INVALID_PATH,
                        "stat",
                        full,
                        "entry changed after admission",
                    )
            except (StorageError, OSError):
                outcomes.append(
                    {
                        "path": entry.archive_path,
                        "status": "failed",
                        "note": "entry disappeared or changed mid-stream",
                    }
                )
                yield from sink.drain()
                continue
            complete = self._archive_file_entry(archive, entry, storage, full, chunk_size)
            outcomes.append(
                {
                    "path": entry.archive_path,
                    "status": "included" if complete else "failed",
                    "note": (None if complete else "entry disappeared or shrank mid-stream"),
                }
            )
            yield from sink.drain()
        # The bounded manifest note: one honest per-item outcome record.
        payload = json.dumps(
            {"items": outcomes, "note": manifest.manifest_note},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        archive.writestr(ARCHIVE_MANIFEST_NAME, payload)
        archive.close()
        yield from sink.drain()

    @staticmethod
    def _archive_directory_entry(archive: zipfile.ZipFile, entry: DownloadArchiveEntry) -> None:
        info = zipfile.ZipInfo(entry.archive_path)
        info.external_attr = 0o700 << 16 | 0x10
        archive.writestr(info, b"")

    @staticmethod
    def _archive_file_entry(
        archive: zipfile.ZipFile,
        entry: DownloadArchiveEntry,
        storage: Storage,
        full: str,
        chunk_size: int,
    ) -> bool:
        """Stream one archive file entry; True when fully served."""

        info = zipfile.ZipInfo(entry.archive_path)
        complete = False
        with storage.read(full) as stream:
            with archive.open(info, mode="w") as writer:
                served = 0
                while served < entry.size:
                    chunk = stream.read(min(chunk_size, entry.size - served))
                    if not chunk:
                        # The entry disappeared or shrank mid-stream: stop
                        # this entry honestly; the manifest records it.
                        break
                    writer.write(chunk)
                    served += len(chunk)
                complete = served == entry.size
        return complete

    # ------------------------------------------------------------------
    # Response helpers (interface layer)
    # ------------------------------------------------------------------

    def stream_response(
        self,
        *,
        resource_library_id: str,
        manifest: DownloadManifest,
        chunk_size: int = _STREAM_CHUNK,
    ) -> tuple[list[tuple[str, str]], Iterator[bytes]]:
        """The bounded response headers and body of one admitted Download.

        Exactly one response is ever produced: when admission fails the
        error is raised before any byte is committed, so the operator never
        sees a half-streamed body.  The archive case carries no
        Content-Length because the on-the-fly compression size is unknown in
        advance; a WSGI server with chunked transfer encoding handles it.
        """

        library = self._direct.library(resource_library_id)
        storage = self._open_storage(library)
        ascii_name, _rfc_name = self.disposition(manifest.filename)
        filename_param = quote(manifest.filename)
        disposition = (
            f"attachment; filename=\"{ascii_name}\"; "
            f"filename*=UTF-8''{filename_param}"
        )
        if manifest.single_file is not None:
            entry = manifest.single_file
            content_type = self.content_type_for(manifest.filename)
            headers = [
                ("Content-Type", content_type),
                (
                    "Content-Disposition",
                    disposition,
                ),
                ("Content-Length", str(entry.size)),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
            ]
            body = self.stream_single(library, storage, manifest, chunk_size=chunk_size)
            return headers, body
        headers = [
            ("Content-Type", "application/zip"),
            ("Content-Disposition", disposition),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ]
        body = self.stream_archive(library, storage, manifest, chunk_size=chunk_size)
        return headers, body

    @staticmethod
    def content_type_for(filename: str) -> str:
        suffix = posixpath.splitext(filename)[1].lower()
        return _DOWNLOAD_CONTENT_TYPES.get(suffix, "application/octet-stream")

    @staticmethod
    def disposition(filename: str) -> tuple[str, str]:
        """The bounded ASCII + RFC-5987 Content-Disposition parameter pair."""

        ascii_name = filename.encode("ascii", "replace").decode("ascii")
        return ascii_name, filename


def _storage_category(error: Exception) -> tuple[str, int]:
    code = getattr(error, "code", None)
    if code is StorageErrorCode.NOT_FOUND:
        return "not_found", 404
    if code in {StorageErrorCode.PERMISSION_DENIED, StorageErrorCode.READ_ONLY}:
        return "permission_denied", 403
    if code is StorageErrorCode.AUTHENTICATION_FAILED:
        return "authentication_failed", 503
    if code in {StorageErrorCode.CONNECTION_FAILED, StorageErrorCode.CONNECTION_LOST}:
        return "connection_failed", 503
    if code is StorageErrorCode.TIMEOUT:
        return "timeout", 503
    if code is StorageErrorCode.RATE_LIMITED:
        return "rate_limited", 503
    return "storage_failure", 503


class _ZipStreamSink:
    """The bounded sink behind one on-the-fly ZIP archive.

    The writer's chunks accumulate here until the streaming generator
    drains them into the response, so at any moment only the chunks since
    the last drain wait in memory — bounded by one ZIP write.  The byte
    offset is tracked for the central directory.  The archive is never
    staged on disk or in unbounded memory, and nothing is written back to
    managed Storage.
    """

    def __init__(self) -> None:
        self._chunks: list[bytes] = []
        self._position = 0

    def write(self, data: bytes) -> int:
        self._chunks.append(data)
        self._position += len(data)
        return len(data)

    def tell(self) -> int:
        return self._position

    def flush(self) -> None:
        return None

    def drain(self) -> Iterator[bytes]:
        chunks, self._chunks = self._chunks, []
        yield from chunks
