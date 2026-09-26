#!/usr/bin/env python3
"""Docker proof: start before Active, checked-activate, then execute OpenList Move.

The committed candidate's real API and resident Worker are used.  A bounded
in-process HTTP service implements only the OpenList v4 endpoints needed by
this proof; no production credentials, media or remote service are accessed.
The Worker container must stay identical across activation and execution.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

from docker_files_transfer_impact_smoke_test import (
    build_candidate_image,
    image_exists,
    run_docker,
)
from docker_health_smoke_test import json_request, service_records, wait_for_services_healthy
from docker_smoke_test import compose_environment, free_port, wait_for_api, wait_until

ROOT = Path(__file__).resolve().parents[1]
SERVICES = {"api", "worker", "scheduler", "notification-worker"}


class OpenListState:
    def __init__(self, token: str) -> None:
        self.token = token
        self.lock = threading.Lock()
        self.entries: dict[str, tuple[bool, bytes]] = {
            "/Downloads": (True, b""),
            "/Downloads/Movies": (True, b""),
            "/Downloads/resident.mkv": (False, b"resident-openlist"),
        }
        self.move_entered = threading.Event()
        self.move_calls = 0

    @staticmethod
    def item(path: str, value: tuple[bool, bytes], *, raw_url: str | None = None) -> dict:
        directory, payload = value
        document = {
            "name": PurePosixPath(path).name,
            "size": 0 if directory else len(payload),
            "is_dir": directory,
            "modified": "2026-09-26T00:00:00Z",
        }
        if raw_url is not None:
            document["raw_url"] = raw_url
        return document


def handler_for(state: OpenListState):
    class Handler(BaseHTTPRequestHandler):
        def _authorized(self) -> bool:
            return self.headers.get("Authorization") == state.token

        def _reply(self, data: object = None, *, code: int = 200, message: str = "success") -> None:
            payload = json.dumps({"code": code, "message": message, "data": data}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            value = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(value, dict):
                raise ValueError("request body must be an object")
            return value

        def do_GET(self) -> None:  # noqa: N802
            if not self._authorized():
                self.send_error(401)
                return
            if self.path == "/ping":
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            if not self._authorized():
                self.send_error(401)
                return
            body = self._body()
            with state.lock:
                if self.path == "/api/fs/get":
                    path = str(body.get("path", ""))
                    value = state.entries.get(path)
                    if value is None:
                        self._reply(code=404, message="not found")
                    else:
                        self._reply(state.item(path, value))
                    return
                if self.path == "/api/fs/list":
                    parent = str(body.get("path", "")).rstrip("/")
                    prefix = f"{parent}/"
                    children = [
                        state.item(path, value)
                        for path, value in sorted(state.entries.items())
                        if path.startswith(prefix) and "/" not in path[len(prefix) :]
                    ]
                    self._reply({"content": children, "total": len(children)})
                    return
                if self.path == "/api/fs/move":
                    source_dir = str(body.get("src_dir", "")).rstrip("/")
                    target_dir = str(body.get("dst_dir", "")).rstrip("/")
                    names = body.get("names")
                    if not isinstance(names, list) or len(names) != 1:
                        self._reply(code=400, message="invalid names")
                        return
                    source = f"{source_dir}/{names[0]}"
                    target = f"{target_dir}/{names[0]}"
                    if source not in state.entries:
                        self._reply(code=404, message="not found")
                        return
                    if target in state.entries:
                        self._reply(code=409, message="file exists")
                        return
                    state.move_calls += 1
                    state.move_entered.set()
                else:
                    self._reply(code=404, message="not found")
                    return
            # Keep a real adapter request blocked past Worker staleness while
            # the transfer lease/registration keeper runs.
            time.sleep(12)
            with state.lock:
                state.entries[target] = state.entries.pop(source)
            self._reply({})

        def log_message(self, *_args) -> None:
            return None

    return Handler


def prepare(root: Path, api_token: str, openlist_token: str, port: int) -> tuple[Path, ...]:
    source_root = root / "media" / "incoming"
    target_root = root / "media" / "organized"
    source_root.mkdir(parents=True)
    target_root.mkdir(parents=True)
    source_root.chmod(0o755)
    target_root.chmod(0o777)
    document = json.loads(
        subprocess.check_output(
            [sys.executable, str(ROOT / "scripts" / "make_deployment_config.py")], text=True
        )
    )
    document["api"] = {
        "principals": [
            {
                "id": "admin",
                "tokenEnv": "MEDIAFLOW_API_TOKEN",
                "roles": ["admin"],
                "enabled": True,
            }
        ]
    }
    document["automation"]["workerPollSeconds"] = 0.2
    document["storages"] = [
        {
            "id": "openlist",
            "name": "Lifecycle OpenList",
            "type": "openlist",
            "baseUrl": f"http://host.docker.internal:{port}",
            "tokenEnv": "OPENLIST_TOKEN",
            "rootPath": "/Downloads",
            "readOnly": False,
            "connectTimeout": 3,
            "requestTimeout": 30,
            "maxConcurrency": 2,
            "maxRetries": 0,
            "pageSize": 100,
        }
    ]
    document["resourceLibraries"] = [
        {
            "id": "source",
            "name": "OpenList source",
            "storageId": "openlist",
            "storagePath": "",
            "enabled": True,
            "extensions": ["mkv"],
        },
        {
            "id": "destination",
            "name": "OpenList destination",
            "storageId": "openlist",
            "storagePath": "Movies",
            "enabled": True,
            "extensions": ["mkv"],
        },
    ]
    for library in document["mediaLibraries"]:
        library["storageId"] = "openlist"
    config = root / "mediaflow.json"
    config.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    config.chmod(0o644)
    environment_file = root / "deployment.env"
    environment_file.write_text(
        f"MEDIAFLOW_API_TOKEN={api_token}\nOPENLIST_TOKEN={openlist_token}\n",
        encoding="utf-8",
    )
    environment_file.chmod(0o644)
    override = root / "compose.lifecycle.yaml"
    override.write_text(
        "services:\n"
        "  api:\n"
        '    extra_hosts: ["host.docker.internal:host-gateway"]\n'
        "  worker:\n"
        '    extra_hosts: ["host.docker.internal:host-gateway"]\n',
        encoding="utf-8",
    )
    return config, environment_file, source_root, target_root, override


def checked_activate(base: str, token: str, config: Path) -> dict:
    document = json.loads(config.read_text(encoding="utf-8"))
    status, draft = json_request(
        base, "/api/v1/configuration/drafts", token, method="POST", body={"document": document}
    )
    if status != 201:
        raise RuntimeError(f"Draft import failed: HTTP {status}: {draft}")
    revision = urllib.parse.quote(draft["revisionId"])
    status, validated = json_request(
        base, f"/api/v1/configuration/revisions/{revision}/validate", token, method="POST", body={}
    )
    if status != 200:
        raise RuntimeError(f"validation failed: HTTP {status}: {validated}")
    evidence = {
        "expectedVersion": validated["version"],
        "expectedDigest": validated["digest"],
    }
    for storage_id in ("openlist",):
        status, result = json_request(
            base,
            f"/api/v1/configuration/revisions/{revision}/storage-check",
            token,
            method="POST",
            body={**evidence, "storageId": storage_id},
        )
        if status != 200 or result.get("status") != "passed":
            raise RuntimeError(f"Storage check failed: HTTP {status}: {result}")
    status, result = json_request(
        base,
        f"/api/v1/configuration/revisions/{revision}/recognition-strategy-test",
        token,
        method="POST",
        body={**evidence, "resourceLibraryId": "source", "syntheticPath": "resident.mkv"},
    )
    if status != 200 or result.get("status") != "completed":
        raise RuntimeError(f"strategy test failed: HTTP {status}: {result}")
    status, result = json_request(
        base,
        f"/api/v1/configuration/revisions/{revision}/destination-precheck",
        token,
        method="POST",
        body={
            **evidence,
            "recognitionType": "C",
            "sample": {
                "title": "Resident",
                "mediaType": "movie",
                "year": 2026,
                "genres": ["Test"],
                "extension": "mkv",
            },
        },
    )
    if status != 200 or result.get("status") != "completed":
        raise RuntimeError(f"destination precheck failed: HTTP {status}: {result}")
    status, active = json_request(
        base,
        f"/api/v1/configuration/revisions/{revision}/activate",
        token,
        method="POST",
        body={"expectedVersion": validated["version"], "checked": True},
    )
    if status != 200 or active.get("status") != "active":
        raise RuntimeError(f"checked activation failed: HTTP {status}: {active}")
    return active


def lifecycle(project: str, image: str, keep: bool) -> None:
    api_token = secrets.token_urlsafe(24)
    openlist_token = secrets.token_urlsafe(24)
    api_port, openlist_port = free_port(), free_port()
    state = OpenListState(openlist_token)
    server = ThreadingHTTPServer(("0.0.0.0", openlist_port), handler_for(state))
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    with tempfile.TemporaryDirectory(prefix="mediaflow-transfer-lifecycle-") as directory:
        root = Path(directory)
        os.chmod(root, 0o755)
        config, env_file, source_root, target_root, override = prepare(
            root, api_token, openlist_token, openlist_port
        )
        environment = compose_environment(
            root,
            image,
            config_file=config,
            environment_file=env_file,
            source_root=source_root,
            target_root=target_root,
            api_port=api_port,
        )
        command = [
            "docker",
            "compose",
            "-f",
            str(ROOT / "compose.yaml"),
            "-f",
            str(override),
            "--project-name",
            project,
        ]
        try:
            run_docker([*command, "up", "-d", "--no-build"], environment=environment)
            wait_for_services_healthy(command, environment, expected=SERVICES)
            base = f"http://127.0.0.1:{api_port}"
            wait_for_api(base, api_token)
            worker_id = service_records(command, environment)["worker"].get("ID")
            status, readiness = json_request(base, "/api/v1/workers/readiness", api_token)
            work = readiness.get("workReadiness") or {}
            if status != 200 or readiness.get("currentActiveAvailable") is not False:
                raise RuntimeError(f"pre-activation readiness is untruthful: {readiness}")
            if not (work.get("resourceFilesTransfer") or {}).get("ready"):
                raise RuntimeError(f"pre-activation transfer consumer is unavailable: {readiness}")

            checked_activate(base, api_token, config)
            query = "path=resident.mkv&to=destination&toPath=&operation=move&conflict=fail"
            status, impact = json_request(
                base, f"/api/v1/resource-libraries/source/files/transfer-impact?{query}", api_token
            )
            if status != 200:
                raise RuntimeError(f"transfer impact failed: HTTP {status}: {impact}")
            status, admitted = json_request(
                base,
                "/api/v1/resource-libraries/source/files/transfers",
                api_token,
                method="POST",
                body={
                    "operation": "move",
                    "paths": ["resident.mkv"],
                    "destinationResourceLibraryId": "destination",
                    "destinationDirectory": "",
                    "conflictMode": "fail",
                    "manifestDigest": impact["manifestDigest"],
                },
            )
            if status != 202:
                raise RuntimeError(f"transfer admission failed: HTTP {status}: {admitted}")
            task_id = admitted["taskId"]
            if not state.move_entered.wait(30):
                raise RuntimeError("the real OpenList Move request was not observed")
            time.sleep(10.5)
            status, during = json_request(base, "/api/v1/workers/readiness", api_token)
            if status != 200 or not (during.get("baseReadiness") or {}).get("ready"):
                raise RuntimeError(f"Worker registration became stale during slow Move: {during}")

            terminal: dict = {}

            def completed() -> bool:
                nonlocal terminal
                status_code, terminal = json_request(
                    base,
                    f"/api/v1/resource-libraries/source/files/transfers/{task_id}",
                    api_token,
                )
                return status_code == 200 and terminal.get("terminal") is True

            wait_until(completed, timeout=90, description="OpenList Move terminal projection")
            if terminal.get("status") != "SUCCESS":
                raise RuntimeError(f"OpenList Move did not succeed: {terminal}")
            with state.lock:
                if "/Downloads/resident.mkv" in state.entries:
                    raise RuntimeError("OpenList Move left the source entry")
                if (
                    state.entries.get("/Downloads/Movies/resident.mkv", (True, b""))[1]
                    != b"resident-openlist"
                ):
                    raise RuntimeError("OpenList Move target does not match source data")
                if state.move_calls != 1:
                    raise RuntimeError(f"OpenList Move was issued {state.move_calls} times")
            if service_records(command, environment)["worker"].get("ID") != worker_id:
                raise RuntimeError("Worker container identity changed after activation")
            print("Docker transfer lifecycle acceptance passed.")
        finally:
            if not keep:
                run_docker(
                    [*command, "down", "-v", "--remove-orphans"],
                    environment=environment,
                    check=False,
                )
    server.shutdown()
    server.server_close()
    server_thread.join(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="mediaflow:task39-5-lifecycle")
    parser.add_argument("--keep", action="store_true")
    arguments = parser.parse_args()
    if shutil.which("docker") is None:
        print("Docker is unavailable; transfer lifecycle acceptance SKIP")
        return 0
    if not image_exists(arguments.image):
        build_candidate_image(arguments.image)
    suffix = f"{os.getpid()}-{int(time.time())}"
    lifecycle(f"mediaflow-transfer-lifecycle-{suffix}", arguments.image, arguments.keep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
