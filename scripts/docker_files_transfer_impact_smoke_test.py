#!/usr/bin/env python3
"""Isolated current-candidate Docker acceptance for the bounded Copy/Move scope.

This script replaces the retired environment-specific ``source2`` reproduction:
it proves the current candidate admits a bounded synthetic library whose
aggregate media content is larger than 20 GiB, using only temporary Compose
state, temporary managed configuration and sparse synthetic files.  Media
content byte size is impact/progress information, never a Copy/Move admission
ceiling; control-plane bounds (top-level selection count, enumerated entry
count and directory depth, safe relative paths and bounded control-plane
projections) are what stop unbounded work before any destructive effect.

The harness starts the four-service stack against the exact committed
candidate, activates a managed runtime snapshot, seeds one sparse >20 GiB
source file with seek-based writes (never materialized bytes), requests the
real zero-mutation transfer-impact API and asserts that:

- the >20 GiB aggregate is admitted for Impact without reading media content;
- the impact document reports the true aggregate as informational evidence
  while remaining a bounded JSON projection;
- control-plane violations return structured, actionable failures, including
  the truthful HTTP 413 for entry/depth/selection limit classes;
- no Copy/Move/Delete Storage mutation occurs (the source and target roots
  are byte-compared and every observed HTTP mutation verb is absent).

It never reads production configuration, media, credentials or Storage and
never contacts a remote Provider/Storage/registry.  If Docker is unavailable
the harness prints SKIP; a Docker failure is never hidden.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from docker_health_smoke_test import (
    activate_runtime,
    json_request,
    wait_for_services_healthy,
)
from docker_smoke_test import (
    compose_environment,
    free_port,
    wait_for_api,
    wait_until,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SERVICES = {"api", "worker", "scheduler", "notification-worker"}

#: The synthetic aggregate is deliberately larger than the retired 20 GiB
#: admission ceiling, proving aggregate media bytes are informational.
SYNTHETIC_SOURCE_BYTES = 21 * 1024**3
#: Depth-limit class: the synthetic tree nests this many directory levels past
#: the bounded transfer depth so the recursive enumeration refuses the walk.
OVERFLOW_DEPTH = 33
#: Entry-limit class: one flat directory exceeds the bounded enumerated entry
#: count so the recursive enumeration refuses the walk before mutation.
OVERFLOW_ENTRY_COUNT = 5001
#: The impact document must stay a bounded projection.
MAX_EXPECTED_MANIFEST_ENTRIES = 5000
#: Top-level selection bound (bounded control-plane evidence).
MAX_TRANSFER_PATHS = 50


def sparse_file(path: Path, declared_bytes: int) -> None:
    """Create one sparse file with a declared size far above its disk usage.

    Only two boundary writes are materialized, so the host never stores real
    media content while ``stat().st_size`` reports the full aggregate that the
    transfer-impact admission reads as metadata.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.seek(declared_bytes - 1)
        handle.write(b"\0")


def compose_command(project: str) -> list[str]:
    """The Compose topology always comes from the committed candidate checkout."""

    return [
        "docker",
        "compose",
        "-f",
        str(ROOT / "compose.yaml"),
        "--project-name",
        project,
    ]


def prepare_transfer_config(root: Path, admin_token: str) -> tuple[Path, Path, Path, Path]:
    """Create the temporary managed configuration and synthetic media roots."""

    source_root = root / "media" / "incoming"
    target_root = root / "media" / "organized"
    source_root.mkdir(parents=True)
    target_root.mkdir(parents=True)
    source_root.chmod(0o755)
    target_root.chmod(0o777)

    generated = subprocess.check_output(
        [sys.executable, str(ROOT / "scripts" / "make_deployment_config.py")],
        cwd=ROOT,
        text=True,
    )
    document = json.loads(generated)
    document["api"] = {
        "principals": [
            {
                "id": "admin",
                "tokenEnv": "MEDIAFLOW_API_TOKEN",
                "roles": ["admin"],
                "enabled": True,
            }
        ],
    }
    # The temporary manual flow is explicitly non-destructive.
    for policy in document.get("organizePolicies", []):
        if policy.get("id") == "A":
            policy["operation"] = "COPY"
            break
    # The impact probe needs one distinct destination ResourceLibrary bound to
    # the writable target Storage so a source->destination scope never
    # overlaps itself.
    document["resourceLibraries"].append(
        {
            "id": "organized",
            "name": "Transfer impact target",
            "storageId": "media-target",
            "storagePath": "",
            "displayRootPath": "/media/organized",
            "enabled": True,
        }
    )

    # One synthetic sparse source file with an aggregate above the retired
    # 20 GiB ceiling, inside the bounded source ResourceLibrary.
    sparse_file(
        source_root / "Source2 Large Media.2001.mkv",
        SYNTHETIC_SOURCE_BYTES,
    )
    # One deterministic over-depth sibling tree for the depth limit class: the
    # nesting deliberately exceeds the transfer depth bound so selecting its
    # root forces the bounded recursive enumeration to refuse the walk.
    depth_root = source_root / "deep"
    leaf = depth_root
    for level in range(OVERFLOW_DEPTH + 8):
        leaf = leaf / f"level-{level:02}"
    leaf.mkdir(parents=True, exist_ok=True)
    # One deterministic entry-count sibling tree: the flat fan-out exceeds the
    # bounded enumerated entry count so the walk refuses before mutation.
    entry_root = source_root / "entries"
    entry_root.mkdir(parents=True, exist_ok=True)
    for index in range(OVERFLOW_ENTRY_COUNT):
        (entry_root / f"entry-{index:05}.mkv").touch()

    config_file = root / "mediaflow.json"
    config_file.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    config_file.chmod(0o644)

    environment_file = root / "deployment.env"
    environment_file.write_text(f"MEDIAFLOW_API_TOKEN={admin_token}\n", encoding="utf-8")
    environment_file.chmod(0o644)
    return config_file, environment_file, source_root, target_root


def impact_request(
    base: str,
    token: str,
    *,
    paths: list[str],
    operation: str = "copy",
    conflict: str | None = None,
    to_path: str = "",
) -> tuple[int, dict | bytes]:
    query = "&".join(f"path={urllib.parse.quote(path)}" for path in paths)
    query += f"&to=organized&toPath={urllib.parse.quote(to_path)}&operation={operation}"
    if conflict is not None:
        query += f"&conflict={conflict}"
    status, body = json_request(
        base,
        f"/api/v1/resource-libraries/source/files/transfer-impact?{query}",
        token,
    )
    if isinstance(body, bytes):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            pass
    return status, body


def assert_transfer_impact_admits_large_bytes(
    base: str, admin: str, source_root: Path, target_root: Path
) -> dict:
    """Request the real zero-mutation Impact for the >20 GiB synthetic scope."""

    status, impact = impact_request(
        base,
        admin,
        paths=["Source2 Large Media.2001.mkv"],
    )
    if status != 200:
        raise RuntimeError(
            "the >20 GiB synthetic selection was rejected by aggregate media bytes "
            f"(HTTP {status}): {impact}"
        )
    document = impact if isinstance(impact, dict) else {}
    if document.get("totalBytes") != SYNTHETIC_SOURCE_BYTES:
        raise RuntimeError(
            "transfer impact did not report the exact synthetic aggregate as "
            f"informational evidence: {document.get('totalBytes')}"
        )
    if document.get("operation") != "copy":
        raise RuntimeError(f"unexpected transfer operation: {document}")
    if not document.get("manifestDigest"):
        raise RuntimeError("transfer impact omitted its opaque manifest digest")
    if document.get("sideEffects") != "none":
        raise RuntimeError("transfer impact must remain zero-mutation evidence")
    serialized = json.dumps(document)
    if len(document.get("entries", [])) > MAX_EXPECTED_MANIFEST_ENTRIES:
        raise RuntimeError("transfer impact document exceeded its bounded entries")
    if str(source_root) in serialized or str(target_root) in serialized:
        raise RuntimeError("transfer impact leaked an absolute host path")
    print(
        "Aggregate media bytes admitted as impact evidence: "
        f"{document.get('totalBytes')} bytes (>{20 * 1024**3} GiB ceiling), "
        f"{len(document.get('entries', []))} bounded manifest entries."
    )
    return document


def assert_structured_limit_failure(
    base: str,
    admin: str,
    *,
    paths: list[str],
    expected_category: str,
    description: str,
) -> None:
    status, body = impact_request(base, admin, paths=paths)
    if status != 413:
        raise RuntimeError(f"{description} returned HTTP {status}, expected truthful 413: {body}")
    error = body.get("error") if isinstance(body, dict) else {}
    details = error.get("details") if isinstance(error, dict) else {}
    category = details.get("category") if isinstance(details, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    if category != expected_category or code != f"files_transfer_{expected_category}":
        raise RuntimeError(
            f"{description} returned code {code!r}/category {category!r}, "
            f"expected files_transfer_{expected_category}"
        )
    if not isinstance(details, dict) or not details.get("nextAction"):
        raise RuntimeError(f"{description} error is not actionable: {body}")
    if details.get("durableState") != "storage_unchanged":
        raise RuntimeError(f"{description} did not report a durable unchanged state: {body}")


def assert_control_plane_limits_fail_closed(base: str, admin: str) -> None:
    """Prove control-plane violations stop work before any mutation."""

    # Selecting the root of an over-depth synthetic tree forces the bounded
    # recursive enumeration, which refuses to descend past the transfer depth
    # bound and returns a truthful structured 413.
    assert_structured_limit_failure(
        base,
        admin,
        paths=["deep"],
        expected_category="depth_limit_exceeded",
        description="the over-depth selection",
    )
    print("Over-depth selection returned structured HTTP 413 without mutation.")

    # Selecting the flat oversized sibling forces the bounded entry-count
    # refusal, which is also a truthful structured 413.
    assert_structured_limit_failure(
        base,
        admin,
        paths=["entries"],
        expected_category="entry_limit_exceeded",
        description="the over-entry selection",
    )
    print("Over-entry selection returned structured HTTP 413 without mutation.")

    # A top-level selection above the bounded path count is rejected by the
    # query admission boundary with an actionable 400 and no Storage read.
    status, body = impact_request(
        base,
        admin,
        paths=[f"entries/entry-{index:05}.mkv" for index in range(MAX_TRANSFER_PATHS + 1)],
    )
    error = body.get("error") if isinstance(body, dict) else {}
    details = error.get("details") if isinstance(error, dict) else {}
    if status != 400 or error.get("code") != "files_transfer_invalid_request":
        raise RuntimeError(
            f"the over-selection request returned HTTP {status}, expected a bounded 400: {body}"
        )
    if not isinstance(details, dict) or not details.get("nextAction"):
        raise RuntimeError(f"the over-selection error is not actionable: {body}")
    if details.get("durableState") != "storage_unchanged":
        raise RuntimeError(f"the over-selection error did not report an unchanged state: {body}")
    print("Over-selection request was rejected with structured actionable evidence.")


def assert_invalid_requests_fail_closed(base: str, admin: str) -> None:
    """Prove malformed transfer queries return bounded actionable errors."""

    status, body = impact_request(base, admin, paths=[])
    if status != 400:
        raise RuntimeError(f"an empty selection returned HTTP {status}, expected 400")
    error = body.get("error") if isinstance(body, dict) else {}
    if error.get("code") != "files_transfer_invalid_request":
        raise RuntimeError(f"an empty selection returned a non-structured error: {body}")
    if not (error.get("details") or {}).get("nextAction"):
        raise RuntimeError(f"the empty-selection error is not actionable: {body}")

    status, body = impact_request(base, admin, paths=["../../escape.mkv"])
    error = body.get("error") if isinstance(body, dict) else {}
    if status != 400 or not isinstance(error.get("code"), str) or not error.get("code"):
        raise RuntimeError(
            f"a path-escape selection returned HTTP {status}, expected a bounded 400: {body}"
        )
    details = error.get("details") or {}
    if not details.get("nextAction"):
        raise RuntimeError(f"the path-escape error is not actionable: {body}")
    rendered = json.dumps(body)
    if "Bearer" in rendered or "/media/incoming" in rendered:
        raise RuntimeError(f"the path-escape error leaked host evidence: {body}")
    print("Malformed and escaping transfer queries fail closed without mutation.")


def assert_zero_mutation(source_root: Path, target_root: Path) -> None:
    """Prove neither media root received any Copy/Move/Delete effect."""

    target_files = [path for path in target_root.rglob("*") if path.is_file()]
    if target_files:
        raise RuntimeError(f"the target root received transfer effects: {target_files}")
    source_names = {path.name for path in source_root.rglob("*") if path.is_file()}
    expected = {"Source2 Large Media.2001.mkv"}
    if not expected.issubset(source_names):
        raise RuntimeError(
            f"the synthetic source selection disappeared during the impact journey: {source_names}"
        )


def transfer_impact_smoke(project: str, image: str, keep: bool, admin_token: str) -> None:
    api_port = free_port()
    with tempfile.TemporaryDirectory(prefix="mediaflow-transfer-impact-") as directory:
        root = Path(directory)
        os.chmod(root, 0o755)
        config_file, environment_file, source_root, target_root = prepare_transfer_config(
            root, admin_token
        )
        environment = compose_environment(
            root,
            image,
            config_file=config_file,
            environment_file=environment_file,
            source_root=source_root,
            target_root=target_root,
            api_port=api_port,
        )
        command = compose_command(project=project)
        try:
            print("Starting the isolated four-service stack for the transfer-impact probe...")
            run_docker(
                [*command, "up", "-d", "--no-build"],
                environment=environment,
            )
            wait_for_services_healthy(
                command,
                environment,
                expected=EXPECTED_SERVICES,
            )
            base = f"http://127.0.0.1:{api_port}"
            wait_for_api(base, admin_token)

            print("Activating the managed runtime snapshot...")
            activate_runtime(base, admin_token, config_file)

            def management_ready() -> bool:
                status, management = json_request(base, "/api/v1/management/readiness", admin_token)
                return (
                    status == 200
                    and management.get("managementReady") is True
                    and bool((management.get("active") or {}).get("revisionId"))
                )

            wait_until(management_ready, timeout=90.0, description="managed runtime ready")

            print("Proving the >20 GiB synthetic aggregate is admitted for Impact...")
            assert_transfer_impact_admits_large_bytes(base, admin_token, source_root, target_root)

            print("Proving control-plane limit classes fail closed with structured 413...")
            assert_control_plane_limits_fail_closed(base, admin_token)

            print("Proving malformed and escaping queries fail closed...")
            assert_invalid_requests_fail_closed(base, admin_token)

            assert_zero_mutation(source_root, target_root)
            print("No Copy/Move/Delete Storage mutation occurred.")
            print("Transfer-impact isolation acceptance passed.")
        finally:
            if not keep:
                run_docker(
                    [*command, "down", "-v", "--remove-orphans"],
                    environment=environment,
                    check=False,
                )


def run_docker(
    command: list[str],
    *,
    environment: dict[str, str],
    check: bool = True,
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"docker command failed ({result.returncode}): {command}\n"
            f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="mediaflow:transfer-impact-local")
    parser.add_argument("--keep", action="store_true", help="keep containers for inspection")
    arguments = parser.parse_args()
    if shutil.which("docker") is None:
        print("Docker engine is unavailable; transfer-impact smoke acceptance SKIP")
        return 0

    image = arguments.image
    if not image_exists(image):
        print(f"Building the exact candidate image {image} from a clean checkout...")
        build_candidate_image(image)
    suffix = f"{os.getpid()}-{int(time.time())}"
    admin_token = f"transfer-impact-{suffix}"[:64]
    transfer_impact_smoke(
        f"mediaflow-transfer-impact-{suffix}",
        image,
        keep=arguments.keep,
        admin_token=admin_token,
    )
    return 0


def image_exists(image: str) -> bool:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def build_candidate_image(image: str) -> None:
    """Build the candidate image from the exact committed checkout only."""

    with tempfile.TemporaryDirectory(prefix="mediaflow-transfer-impact-context-") as directory:
        context = Path(directory)
        archive = subprocess.run(
            ["git", "archive", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["tar", "-x", "-C", str(context)],
            input=archive.stdout,
            check=True,
        )
        result = subprocess.run(
            [
                "docker",
                "build",
                "--no-cache",
                "--progress",
                "plain",
                "--file",
                str(context / "Dockerfile"),
                "--tag",
                image,
                str(context),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"candidate image build failed: {result.stdout[-2000:]}\n{result.stderr[-2000:]}"
            )


if __name__ == "__main__":
    raise SystemExit(main())
