from __future__ import annotations

import io
import unittest
from datetime import UTC, datetime

from mediaflow.domain.storage import StorageEntryType, StorageError, StorageErrorCode
from mediaflow.infrastructure.s3_storage import (
    Boto3S3Client,
    S3ClientError,
    S3ClientErrorKind,
    S3ClientObject,
    S3ListPage,
    S3Provider,
    S3Storage,
    S3StorageConfig,
)

NOW = datetime(2026, 8, 19, tzinfo=UTC)


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.calls: list[tuple[object, ...]] = []
        self.failure: S3ClientError | None = None
        self.failure_operation: str | None = None
        self.fail_part: int | None = None
        self.fail_complete = False
        self.uploads: dict[str, list[bytes]] = {}
        self.page_limit: int | None = None

    def _fail(self, operation: str) -> None:
        if self.failure and (self.failure_operation is None or self.failure_operation == operation):
            raise self.failure

    def head_bucket(self) -> None:
        self.calls.append(("head_bucket",))
        self._fail("head_bucket")

    def list_objects(
        self, prefix: str, *, delimiter: str, token: str | None, max_keys: int
    ) -> S3ListPage:
        self.calls.append(("list", prefix, delimiter, token, max_keys))
        self._fail("list")
        names: list[tuple[str, str]] = []
        for key in sorted(self.objects):
            if not key.startswith(prefix):
                continue
            remainder = key[len(prefix) :]
            if delimiter in remainder:
                names.append(("prefix", prefix + remainder.split(delimiter, 1)[0] + delimiter))
            else:
                names.append(("object", key))
        names = list(dict.fromkeys(names))
        limit = min(max_keys, self.page_limit or max_keys)
        start = int(token or 0)
        selected = names[start : start + limit]
        next_token = str(start + limit) if start + limit < len(names) else None
        objects = tuple(self._object(value) for kind, value in selected if kind == "object")
        prefixes = tuple(value for kind, value in selected if kind == "prefix")
        return S3ListPage(objects, prefixes, next_token)

    def _object(self, key: str) -> S3ClientObject:
        return S3ClientObject(key, len(self.objects[key]), NOW, f"etag-{len(self.objects[key])}")

    def head_object(self, key: str) -> S3ClientObject:
        self.calls.append(("head", key))
        self._fail("head")
        if key not in self.objects:
            raise S3ClientError(S3ClientErrorKind.NOT_FOUND)
        return self._object(key)

    def get_object(self, key: str):
        self.calls.append(("get", key))
        self._fail("get")
        if key not in self.objects:
            raise S3ClientError(S3ClientErrorKind.NOT_FOUND)
        return io.BytesIO(self.objects[key])

    def put_object(self, key: str, data, *, content_type: str | None = None) -> None:
        self.calls.append(("put", key, content_type))
        self._fail("put")
        if isinstance(data, bytes | bytearray | memoryview):
            self.objects[key] = bytes(data)
        else:
            chunks = []
            while chunk := data.read(1024 * 1024):
                chunks.append(chunk)
            self.objects[key] = b"".join(chunks)

    def create_multipart_upload(self, key: str) -> str:
        self.calls.append(("create_multipart", key))
        self._fail("create_multipart")
        self.uploads["upload-1"] = []
        return "upload-1"

    def upload_part(self, key: str, upload_id: str, part_number: int, data: bytes) -> str:
        self.calls.append(("upload_part", key, upload_id, part_number, len(data)))
        if self.fail_part == part_number:
            raise S3ClientError(S3ClientErrorKind.IO_ERROR)
        self.uploads[upload_id].append(data)
        return f"etag-{part_number}"

    def complete_multipart_upload(self, key: str, upload_id: str, parts) -> None:
        self.calls.append(("complete_multipart", key, upload_id, tuple(parts)))
        if self.fail_complete:
            raise S3ClientError(S3ClientErrorKind.IO_ERROR)
        self.objects[key] = b"".join(self.uploads.pop(upload_id))

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        self.calls.append(("abort_multipart", key, upload_id))
        self.uploads.pop(upload_id, None)

    def copy_object(self, source_key: str, target_key: str) -> None:
        self.calls.append(("copy", source_key, target_key))
        self._fail("copy")
        if source_key not in self.objects:
            raise S3ClientError(S3ClientErrorKind.NOT_FOUND)
        self.objects[target_key] = self.objects[source_key]

    def delete_object(self, key: str) -> None:
        self.calls.append(("delete", key))
        self._fail("delete")
        if key not in self.objects:
            raise S3ClientError(S3ClientErrorKind.NOT_FOUND)
        del self.objects[key]

    def close(self) -> None:
        self.calls.append(("close",))


class S3StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FakeS3Client()
        self.config = S3StorageConfig(
            "s3",
            "S3",
            S3Provider.S3_COMPATIBLE,
            "media",
            "access-secret",
            "secret-secret",
            endpoint="https://s3.invalid",
            root_prefix="downloads",
            multipart_threshold=6 * 1024 * 1024,
            multipart_part_size=5 * 1024 * 1024,
            page_size=100,
        )
        self.storage = S3Storage(self.config, self.client, sleep=lambda _: None)

    def assert_code(self, code: StorageErrorCode, call) -> StorageError:
        with self.assertRaises(StorageError) as raised:
            call()
        self.assertEqual(code, raised.exception.code)
        return raised.exception

    def test_aws_r2_generic_configuration_and_secret_redaction(self) -> None:
        aws = S3StorageConfig("a", "AWS", S3Provider.AWS_S3, "bucket", "ak", "sk")
        r2 = S3StorageConfig(
            "r",
            "R2",
            S3Provider.CLOUDFLARE_R2,
            "bucket",
            "ak",
            "sk",
            endpoint="https://id.r2.cloudflarestorage.com",
        )
        self.assertEqual("us-east-1", aws.effective_region)
        self.assertEqual("auto", r2.effective_region)
        self.assertNotIn("access-secret", repr(self.config))
        self.assertNotIn("secret-secret", repr(self.config))
        with self.assertRaises(ValueError):
            S3StorageConfig("x", "x", S3Provider.AWS_S3, "", "ak", "sk")
        with self.assertRaises(ValueError):
            S3StorageConfig("x", "x", S3Provider.S3_COMPATIBLE, "b", "ak", "sk")

    def test_health_checks_bucket_and_root_prefix(self) -> None:
        self.storage.health_check()
        self.assertEqual("head_bucket", self.client.calls[0][0])
        self.assertEqual(("list", "downloads/", "/", None, 1), self.client.calls[1])

    def test_root_mapping_normalization_unicode_and_traversal(self) -> None:
        self.client.objects["downloads/电影/a b.mkv"] = b"x"
        self.assertEqual("电影/a b.mkv", self.storage.stat("电影//./a b.mkv").path)
        for path in ("../x", "../../x", "folder/../../../x", "/x", "s3://other/x", "C:/x"):
            self.assert_code(
                StorageErrorCode.PATH_TRAVERSAL if ".." in path else StorageErrorCode.INVALID_PATH,
                lambda path=path: self.storage.stat(path),
            )

    def test_list_empty_files_directories_markers_and_pagination(self) -> None:
        self.assertEqual((), self.storage.list(""))
        self.client.page_limit = 100
        for index in range(225):
            self.client.objects[f"downloads/item-{index:03d}"] = bytes([index % 256])
        self.client.objects["downloads/dir/"] = b""
        self.client.objects["downloads/dir/file"] = b"x"
        result = self.storage.list("")
        self.assertEqual(226, len(result))
        self.assertEqual(StorageEntryType.DIRECTORY, result[0].entry_type)
        list_calls = [call for call in self.client.calls if call[0] == "list"]
        self.assertGreaterEqual(len(list_calls), 4)

    def test_list_missing_and_error_mapping(self) -> None:
        self.assert_code(StorageErrorCode.NOT_FOUND, lambda: self.storage.list("missing"))
        for kind, code in (
            (S3ClientErrorKind.PERMISSION_DENIED, StorageErrorCode.PERMISSION_DENIED),
            (S3ClientErrorKind.AUTHENTICATION_FAILED, StorageErrorCode.AUTHENTICATION_FAILED),
            (S3ClientErrorKind.TIMEOUT, StorageErrorCode.TIMEOUT),
        ):
            self.client.failure = S3ClientError(kind)
            self.client.failure_operation = "list"
            self.assert_code(code, lambda: self.storage.list(""))
            self.client.failure = None

    def test_stat_file_logical_directory_marker_and_missing(self) -> None:
        self.client.objects["downloads/file"] = b"abc"
        self.client.objects["downloads/marker/"] = b""
        self.client.objects["downloads/logical/child"] = b"x"
        self.assertEqual(3, self.storage.stat("file").size)
        self.assertTrue(self.storage.stat("marker").is_directory)
        self.assertTrue(self.storage.stat("logical").is_directory)
        self.assert_code(StorageErrorCode.NOT_FOUND, lambda: self.storage.stat("missing"))

    def test_exists_only_hides_not_found(self) -> None:
        self.client.objects["downloads/a"] = b"a"
        self.assertTrue(self.storage.exists("a"))
        self.assertFalse(self.storage.exists("missing"))
        self.client.failure = S3ClientError(S3ClientErrorKind.AUTHENTICATION_FAILED)
        self.client.failure_operation = "head"
        self.assert_code(StorageErrorCode.AUTHENTICATION_FAILED, lambda: self.storage.exists("a"))

    def test_read_stream_success_large_behavior_and_failures(self) -> None:
        payload = b"x" * (2 * 1024 * 1024)
        self.client.objects["downloads/a"] = payload
        with self.storage.read("a") as stream:
            self.assertEqual(payload[:10], stream.read(10))
        self.assert_code(StorageErrorCode.NOT_FOUND, lambda: self.storage.read("missing"))
        for kind, code in (
            (S3ClientErrorKind.PERMISSION_DENIED, StorageErrorCode.PERMISSION_DENIED),
            (S3ClientErrorKind.CONNECTION_LOST, StorageErrorCode.CONNECTION_LOST),
            (S3ClientErrorKind.TIMEOUT, StorageErrorCode.TIMEOUT),
        ):
            self.client.failure = S3ClientError(kind)
            self.client.failure_operation = "get"
            self.assert_code(code, lambda: self.storage.read("a"))
            self.client.failure = None

    def test_read_stream_interruption_is_mapped(self) -> None:
        class Interrupted(io.BytesIO):
            def read(self, size: int = -1) -> bytes:
                raise S3ClientError(S3ClientErrorKind.CONNECTION_LOST)

        self.client.objects["downloads/a"] = b"a"
        self.client.get_object = lambda key: Interrupted(b"a")
        with self.storage.read("a") as stream:
            self.assert_code(StorageErrorCode.CONNECTION_LOST, stream.read)

    def test_small_write_conflict_overwrite_and_directory_conflict(self) -> None:
        self.storage.write("a", io.BytesIO(b"abc"))
        self.assertEqual(b"abc", self.client.objects["downloads/a"])
        self.assert_code(StorageErrorCode.ALREADY_EXISTS, lambda: self.storage.write("a", b"x"))
        self.storage.write("a", b"x", overwrite=True)
        self.storage.create_directory("dir")
        self.assert_code(StorageErrorCode.ALREADY_EXISTS, lambda: self.storage.write("dir", b"x"))

    def test_large_write_uses_multipart_without_unbounded_read(self) -> None:
        class Guarded(io.BytesIO):
            def read(self, size: int = -1) -> bytes:
                if size < 0 or size > 5 * 1024 * 1024:
                    raise AssertionError("unbounded read")
                return super().read(size)

        payload = b"z" * (11 * 1024 * 1024)
        self.storage.write("large", Guarded(payload))
        self.assertEqual(payload, self.client.objects["downloads/large"])
        parts = [call for call in self.client.calls if call[0] == "upload_part"]
        self.assertEqual([1, 2, 3], [call[3] for call in parts])

    def test_multipart_part_and_complete_failure_abort(self) -> None:
        payload = io.BytesIO(b"x" * (7 * 1024 * 1024))
        self.client.fail_part = 2
        self.assert_code(StorageErrorCode.IO_ERROR, lambda: self.storage.write("part", payload))
        self.assertTrue(any(call[0] == "abort_multipart" for call in self.client.calls))
        self.client.fail_part = None
        self.client.fail_complete = True
        self.assert_code(
            StorageErrorCode.IO_ERROR,
            lambda: self.storage.write("complete", io.BytesIO(b"x" * (7 * 1024 * 1024))),
        )
        self.assertGreaterEqual(sum(call[0] == "abort_multipart" for call in self.client.calls), 2)

    def test_create_directory_marker_conflicts_and_readonly(self) -> None:
        self.storage.create_directory("Movies")
        self.assertIn("downloads/Movies/", self.client.objects)
        self.assert_code(
            StorageErrorCode.ALREADY_EXISTS, lambda: self.storage.create_directory("Movies")
        )
        self.client.objects["downloads/file"] = b"x"
        self.assert_code(
            StorageErrorCode.ALREADY_EXISTS, lambda: self.storage.create_directory("file")
        )

    def test_copy_server_side_source_preserved_and_errors(self) -> None:
        self.client.objects["downloads/source"] = b"source"
        self.storage.copy("source", "target")
        self.assertEqual(b"source", self.client.objects["downloads/source"])
        self.assertEqual(b"source", self.client.objects["downloads/target"])
        self.assert_code(
            StorageErrorCode.ALREADY_EXISTS, lambda: self.storage.copy("source", "target")
        )
        self.assert_code(StorageErrorCode.NOT_FOUND, lambda: self.storage.copy("missing", "other"))
        self.client.failure = S3ClientError(S3ClientErrorKind.CONNECTION_LOST)
        self.client.failure_operation = "copy"
        self.assert_code(
            StorageErrorCode.CONNECTION_LOST, lambda: self.storage.copy("source", "other")
        )

    def test_large_server_side_copy_is_explicitly_unsupported(self) -> None:
        self.client.objects["downloads/large"] = b"1234"
        config = S3StorageConfig(
            "s", "S", S3Provider.AWS_S3, "bucket", "ak", "sk", max_single_copy_size=3
        )
        storage = S3Storage(config, self.client)
        self.assert_code(
            StorageErrorCode.UNSUPPORTED_OPERATION, lambda: storage.copy("downloads/large", "x")
        )

    def test_move_copy_verify_delete_success(self) -> None:
        self.client.objects["downloads/source"] = b"source"
        self.storage.move("source", "target")
        self.assertNotIn("downloads/source", self.client.objects)
        self.assertEqual(b"source", self.client.objects["downloads/target"])
        actions = [call[0] for call in self.client.calls]
        self.assertLess(actions.index("copy"), actions.index("delete"))

    def test_move_copy_failure_preserves_source(self) -> None:
        self.client.objects["downloads/source"] = b"source"
        self.client.failure = S3ClientError(S3ClientErrorKind.CONNECTION_LOST)
        self.client.failure_operation = "copy"
        self.assert_code(
            StorageErrorCode.CONNECTION_LOST, lambda: self.storage.move("source", "target")
        )
        self.assertIn("downloads/source", self.client.objects)
        self.assertNotIn("downloads/target", self.client.objects)

    def test_move_delete_failure_is_partial_and_preserves_both(self) -> None:
        self.client.objects["downloads/source"] = b"source"
        self.client.failure = S3ClientError(S3ClientErrorKind.PERMISSION_DENIED)
        self.client.failure_operation = "delete"
        error = self.assert_code(
            StorageErrorCode.IO_ERROR, lambda: self.storage.move("source", "target")
        )
        self.assertIn("partially completed", str(error))
        self.assertIn("downloads/source", self.client.objects)
        self.assertIn("downloads/target", self.client.objects)

    def test_move_target_conflict_never_deletes_source(self) -> None:
        self.client.objects.update({"downloads/source": b"s", "downloads/target": b"t"})
        self.assert_code(
            StorageErrorCode.ALREADY_EXISTS, lambda: self.storage.move("source", "target")
        )
        self.assertEqual(b"s", self.client.objects["downloads/source"])
        self.assertFalse(any(call[0] == "delete" for call in self.client.calls))

    def test_delete_file_empty_marker_and_nonempty_directory_safety(self) -> None:
        self.client.objects["downloads/file"] = b"x"
        self.storage.delete("file")
        self.client.objects["downloads/empty/"] = b""
        self.storage.delete("empty")
        self.client.objects["downloads/full/"] = b""
        self.client.objects["downloads/full/a"] = b"a"
        self.assert_code(StorageErrorCode.ALREADY_EXISTS, lambda: self.storage.delete("full"))
        self.assertIn("downloads/full/a", self.client.objects)
        self.assert_code(StorageErrorCode.NOT_FOUND, lambda: self.storage.delete("missing"))

    def test_readonly_blocks_all_mutations_before_client(self) -> None:
        storage = S3Storage(
            S3StorageConfig("r", "RO", S3Provider.AWS_S3, "bucket", "ak", "sk", read_only=True),
            self.client,
        )
        before = list(self.client.calls)
        operations = (
            lambda: storage.write("a", b"x"),
            lambda: storage.create_directory("a"),
            lambda: storage.copy("a", "b"),
            lambda: storage.move("a", "b"),
            lambda: storage.delete("a"),
        )
        for operation in operations:
            self.assert_code(StorageErrorCode.READ_ONLY, operation)
        self.assertEqual(before, self.client.calls)
        self.assertFalse(storage.capabilities.can_move)

    def test_capabilities_links_and_no_fallback(self) -> None:
        capabilities = self.storage.capabilities
        self.assertTrue(capabilities.can_move and capabilities.can_copy and capabilities.can_delete)
        self.assertFalse(capabilities.can_hard_link or capabilities.can_soft_link)
        self.assert_code(
            StorageErrorCode.UNSUPPORTED_OPERATION, lambda: self.storage.hard_link("a", "b")
        )
        self.assert_code(
            StorageErrorCode.UNSUPPORTED_OPERATION, lambda: self.storage.soft_link("a", "b")
        )

    def test_retry_only_read_operations_and_rate_limit(self) -> None:
        attempts = 0

        def eventually_succeeds(prefix, *, delimiter, token, max_keys):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise S3ClientError(S3ClientErrorKind.RATE_LIMITED, retry_after=0)
            return S3ListPage((), ())

        self.client.list_objects = eventually_succeeds
        self.assertEqual((), self.storage.list(""))
        self.assertEqual(3, attempts)


class ErrorResponse(Exception):
    def __init__(self, code: str, status: int) -> None:
        self.response = {
            "Error": {"Code": code},
            "ResponseMetadata": {"HTTPStatusCode": status, "HTTPHeaders": {}},
        }


class S3ErrorMapperTests(unittest.TestCase):
    def test_structured_service_error_mapping(self) -> None:
        cases = (
            ("NoSuchKey", 404, S3ClientErrorKind.NOT_FOUND),
            ("NoSuchBucket", 404, S3ClientErrorKind.BUCKET_NOT_FOUND),
            ("AccessDenied", 403, S3ClientErrorKind.PERMISSION_DENIED),
            ("InvalidAccessKeyId", 403, S3ClientErrorKind.AUTHENTICATION_FAILED),
            ("SignatureDoesNotMatch", 403, S3ClientErrorKind.AUTHENTICATION_FAILED),
            ("PreconditionFailed", 412, S3ClientErrorKind.ALREADY_EXISTS),
            ("SlowDown", 503, S3ClientErrorKind.RATE_LIMITED),
            ("RequestTimeout", 400, S3ClientErrorKind.TIMEOUT),
            ("ServiceUnavailable", 503, S3ClientErrorKind.CONNECTION_LOST),
            ("InternalError", 500, S3ClientErrorKind.CONNECTION_LOST),
        )
        for code, status, expected in cases:
            with self.subTest(code=code):
                self.assertEqual(
                    expected, Boto3S3Client._map_error(ErrorResponse(code, status)).kind
                )
