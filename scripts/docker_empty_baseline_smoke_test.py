#!/usr/bin/env python3
"""Isolated Docker Compose acceptance for the empty-baseline resident boundary.

This is the real-process proof of the resident-service journey: a fresh
deployment with **no media mount at all** starts the API and all three resident
services from management-only bootstrap, they register and heartbeat, the
Scheduler and Notification Worker report themselves as waiting rather than
failed, an empty baseline is activated, and an eligible configuration published
afterwards is adopted by the *same* running processes — with an eligible
scheduled occurrence and a signed Webhook delivery produced without any restart.

A second, separate stack carries optional confined media mounts present
*before* startup and proves real media work, so a permitted mount-change
recreation is never confused with configuration adoption.

Every check is against a real Python-served HTTP surface.  HTTP mocks are
explicitly not accepted here, because they cannot prove that a process actually
adopted a new configuration.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import ssl
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from docker_smoke_test import free_port, http_request, run, wait_until
from make_deployment_config import make_deployment_configuration, make_management_bootstrap

ROOT = Path(__file__).resolve().parents[1]
PROJECT_PREFIX = "mediaflow-empty-baseline"
IMAGE_TAG = "mediaflow:task40.3-local"
RESIDENT_SERVICES = ("worker", "scheduler", "notification-worker")
ALL_SERVICES = ("api", *RESIDENT_SERVICES)

#: A container that is merely up is not enough: this is the window Compose
#: waits before the first healthcheck, plus the healthcheck cadence itself.
READY_TIMEOUT_SECONDS = 180.0


#: In-container probes.  These read the *running deployment's own* database
#: rather than any host copy, so they prove the real containers registered
#: themselves rather than that a host-side script can see the file.
_RESIDENT_STATE_SCRIPT = ";".join(
    (
        "import json",
        "from mediaflow.application.resident_services import ResidentServiceService",
        "from mediaflow.infrastructure.sqlite_runtime import (SCHEMA_VERSION,SQLiteTaskRepository)",
        "repository=SQLiteTaskRepository('/data/mediaflow.sqlite3')",
        "service=ResidentServiceService(repository, runtime_schema_version=SCHEMA_VERSION)",
        "print(json.dumps(service.deployment_readiness()))",
    )
)

_EMPTY_BASELINE_SCRIPT = ";".join(
    (
        "import json",
        "from mediaflow.application.configuration_snapshot import ("
        "build_first_setup_starter_document)",
        "from mediaflow.infrastructure.runtime_configuration import ("
        "load_minimal_management_bootstrap)",
        "document=json.load(open('/config/mediaflow.json',encoding='utf-8'))",
        "print(json.dumps(build_first_setup_starter_document("
        "load_minimal_management_bootstrap(document))))",
    )
)


#: Host addresses tried, in order, when addressing the host from a container.
#: ``host.docker.internal`` is the documented name but is not routable in every
#: environment, so the Docker bridge gateways are tried as well.
_HOST_CANDIDATES = ("host.docker.internal", "172.17.0.1", "172.18.0.1", "172.19.0.1")


def _discover_reachable_host(self) -> str:
    """Return a host address a real container can open the receiver on.

    Reachability is discovered from *inside a container* rather than from the
    client, because the client and the daemon do not necessarily share a network
    namespace.  A plain TCP probe is sufficient: whether the delivery's TLS is
    actually verified is proved by the delivery itself, not by this probe.
    """

    # A TCP connect proves nothing: a host name can resolve and even complete a
    # connection to something that is not this receiver.  A candidate is
    # therefore accepted only when a container completes a real TLS handshake
    # against this receiver's own certificate and reads its response.
    probe = (
        "import ssl,sys,urllib.request\n"
        "host, port, certificate = sys.argv[1], int(sys.argv[2]), sys.argv[3]\n"
        "try:\n"
        "    context = ssl.create_default_context(cafile=certificate)\n"
        "    request = urllib.request.Request(\n"
        "        'https://%s:%d/hook' % (host, port), data=b'{}', method='POST')\n"
        "    with urllib.request.urlopen(request, timeout=8, context=context) as response:\n"
        "        response.read()\n"
        "except Exception:\n"
        "    raise SystemExit(1)\n"
        "print(host)\n"
    )
    for candidate in _HOST_CANDIDATES:
        # The probe has to trust *this* candidate, so the live certificate is
        # reissued for the candidate before probing.  The final certificate is
        # then reissued once more for the winner, so what the stack mounts is
        # always the certificate that matches the URL it will use.
        self._write_certificate(candidate)
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "bridge",
                "-v",
                f"{self.certificate}:/probe/receiver.pem:ro",
                "python:3.13-slim",
                "python",
                "-c",
                probe,
                candidate,
                str(self.port),
                "/probe/receiver.pem",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return candidate
    raise RuntimeError(
        "no container can reach the local webhook receiver; the signed-delivery "
        "acceptance cannot run in this environment"
    )


def _host_mount_base() -> str | None:
    """Return a directory the Docker daemon can bind-mount from, or ``None``.

    ``None`` lets the platform choose its own temporary directory, which is the
    normal case.  ``MEDIAFLOW_SMOKE_TEMP_DIR`` overrides it for a daemon whose
    mount namespace excludes the default temporary directory.
    """

    override = os.environ.get("MEDIAFLOW_SMOKE_TEMP_DIR")
    if not override:
        return None
    base = Path(override)
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


class WebhookReceiver:
    """A controlled local HTTPS receiver for signed delivery acceptance.

    MediaFlow refuses plain-HTTP webhook endpoints by design, so the receiver
    speaks real TLS with a certificate generated for this run only.  That
    certificate is passed to the *stack's* environment (never committed, never
    written into a configuration document) purely so the isolated container
    can verify this one local endpoint.
    """

    def __init__(self) -> None:
        self.received: list[dict] = []
        self.response_status = 200
        # The certificate is written next to the stack rather than into the
        # platform temporary directory: a container only sees host paths that
        # were bind-mounted, and a host ``/tmp`` the daemon cannot resolve would
        # silently make every TLS verification fail.
        self.directory = Path(
            tempfile.mkdtemp(prefix="mediaflow-empty-baseline-tls-", dir=_host_mount_base())
        )
        self.certificate = self.directory / "receiver.pem"
        self._write_certificate("localhost")
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler contract
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                receiver.received.append(
                    {
                        "path": self.path,
                        "signature": self.headers.get("X-MediaFlow-Signature") or "",
                        "event": self.headers.get("X-MediaFlow-Event") or "",
                        "eventId": self.headers.get("X-MediaFlow-Event-ID") or "",
                        "body": json.loads(body) if body else None,
                    }
                )
                self.send_response(receiver.response_status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            def log_message(self, *arguments):  # noqa: ANN002 - silence the receiver
                return

        self._server = HTTPServer(("0.0.0.0", 0), Handler)
        self._context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._context.load_cert_chain(str(self.certificate))
        self._server.socket = self._context.wrap_socket(self._server.socket, server_side=True)
        # ``host.docker.internal`` is the documented Docker name for the host
        # from inside a container, and the certificate names exactly that, so
        # the signed delivery is verified rather than merely attempted.
        self.port = self._server.server_port
        self._thread = Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    @property
    def url(self) -> str:
        """The HTTPS URL a container can actually reach this receiver on.

        The host is addressed by a name discovered from *inside a real
        container*, because the familiar ``host.docker.internal`` resolves but is
        not routable in every environment.  Assuming it would make the
        signed-delivery step fail for an environment reason that has nothing to
        do with the behaviour under test.
        """

        if self._reachable_host is None:
            self._reachable_host = _discover_reachable_host(self)
            self._write_certificate(self._reachable_host)
            # Reachability probing performs its own request, which must never be
            # mistaken for the delivery under acceptance.
            self.received.clear()
            # The listening socket already holds the first certificate, so the
            # regenerated one must be reloaded into the live context before any
            # container attempts a delivery.
            self._context.load_cert_chain(str(self.certificate))
        return f"https://{self._reachable_host}:{self.port}/hook"

    _reachable_host: str | None = None

    def _write_certificate(self, host: str) -> None:
        """Issue a self-signed certificate naming exactly the reachable host.

        The certificate is generated per run and names the address the container
        will really use, so the delivery's signature and its TLS chain are both
        verified rather than merely attempted.
        """

        is_address = host[0].isdigit()
        alternative = f"IP:{host}" if is_address else f"DNS:{host}"
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(self.certificate),
                "-out",
                str(self.certificate),
                "-days",
                "1",
                "-subj",
                f"/CN={host}",
                "-addext",
                f"subjectAltName={alternative},DNS:localhost,IP:127.0.0.1,DNS:api.themoviedb.org",
            ],
            check=True,
            capture_output=True,
        )
        # The listening socket already holds whatever certificate it bound
        # with, so a reissued one only takes effect once it is reloaded into the
        # live context.  Without this the receiver keeps serving its original
        # certificate and every later probe fails for an unrelated reason.
        context = getattr(self, "_context", None)
        if context is not None:
            context.load_cert_chain(str(self.certificate))

    def stop(self) -> None:
        self._server.shutdown()
        shutil.rmtree(self.directory, ignore_errors=True)


class LocalMetadataProxy:
    """Terminating local TLS fixture; never forwards a request to an external host."""

    def __init__(self, receiver: WebhookReceiver):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(receiver.certificate))
        self.requests = []
        requests = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_CONNECT(self):  # noqa: N802
                if self.path != "api.themoviedb.org:443":
                    self.send_error(403)
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.flush()
                self.connection = context.wrap_socket(self.connection, server_side=True)
                self.rfile = self.connection.makefile("rb")
                self.wfile = self.connection.makefile("wb")
                self.handle_one_request()

            def do_GET(self):  # noqa: N802
                requests.append(self.path)
                movie = {
                    "id": 1,
                    "title": "Acceptance Movie",
                    "original_title": "Acceptance Movie",
                    "release_date": "2025-01-01",
                    "original_language": "en",
                    "overview": "Isolated acceptance",
                    "genre_ids": [28],
                    "genres": [{"id": 28, "name": "Action"}],
                    "production_countries": [{"iso_3166_1": "US", "name": "United States"}],
                    "imdb_id": "tt0000001",
                    "runtime": 100,
                }
                if self.path.startswith("/3/search/movie"):
                    document = {"page": 1, "results": [movie], "total_pages": 1, "total_results": 1}
                elif self.path.startswith("/3/movie/1"):
                    document = movie
                else:
                    self.send_error(404)
                    return
                body = json.dumps(document).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()

            def log_message(self, *arguments):
                pass

        self.server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class Stack:
    """One isolated Compose project with an explicit, inspectable boundary."""

    def __init__(
        self,
        name: str,
        image: str,
        *,
        media: bool,
        receiver: WebhookReceiver | None = None,
    ) -> None:
        self.name = name
        self.image = image
        self.media = media
        # Set before the bootstrap files are written: the receiver
        # certificate is part of the deployment environment, so it has to be
        # known when the environment file is rendered.
        self.receiver = receiver
        # A bind mount is only resolvable where the Docker daemon can actually
        # see the host path.  Some daemons run in a separate mount namespace in
        # which ``/tmp`` is not the same directory the client sees, so the base
        # is configurable rather than assumed.
        self.root = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=_host_mount_base()))
        os.chmod(self.root, 0o755)
        self.data = self.root / "data"
        self.data.mkdir()
        self.api_port = free_port()
        self.token = secrets.token_urlsafe(24)
        self.database = "/data/mediaflow.sqlite3"
        self.config_file = self.root / "mediaflow.json"
        self.environment_file = self.root / "deployment.env"
        self.receiver_mount = self.root / "receiver.pem"
        self.source_root = self.root / "media" / "incoming"
        self.target_root = self.root / "media" / "organized"
        if media:
            self.source_root.mkdir(parents=True)
            self.target_root.mkdir(parents=True)
            self.source_root.chmod(0o777)
            self.target_root.chmod(0o777)
        self.write_bootstrap()
        self.environment = self.compose_environment()
        self.receiver_mount = self.root / "receiver.pem"
        self.overlay = self.root / "compose.receiver.yaml" if receiver is not None else None
        if self.overlay is not None:
            # A read-only certificate mount, added only for this run's local
            # controlled receiver.  It is never part of the committed topology.
            self.overlay.write_text(
                "services:\n"
                + "".join(
                    f"  {name}:\n"
                    f"    volumes:\n"
                    f"      - type: bind\n"
                    f'        source: "{self.receiver_mount}"\n'
                    f"        target: /run/mediaflow/receiver.pem\n"
                    f"        read_only: true\n"
                    for name in ALL_SERVICES
                ),
                encoding="utf-8",
            )
        self.compose = ["docker", "compose", "-f", str(ROOT / "compose.yaml")]
        if media:
            self.compose += ["-f", str(ROOT / "compose.media-mounts.yaml")]
        if self.overlay is not None:
            self.compose += ["-f", str(self.overlay)]
        self.compose += ["--project-name", self.name]

    def write_bootstrap(self) -> None:
        """Render the management-only deployment bootstrap and its secrets.

        Nothing here invents a business object: the document contains only the
        durable database locator and one environment reference for the API
        credential.
        """

        self.config_file.write_text(
            json.dumps(make_management_bootstrap(database_path=self.database), indent=2),
            encoding="utf-8",
        )
        self.config_file.chmod(0o644)
        lines = [
            f"MEDIAFLOW_API_TOKEN={self.token}",
            f"MEDIAFLOW_WEBHOOK_SECRET={self.webhook_secret}",
        ]
        if self.receiver is not None:
            # The isolated stack must trust exactly one local receiver created
            # for this run.  It is a deployment environment value, never part of
            # the managed configuration document.  The certificate is copied
            # into the stack directory and bind-mounted read-only, because a
            # container can only read host paths that were actually mounted.
            shutil.copyfile(self.receiver.certificate, self.receiver_mount)
            self.receiver_mount.chmod(0o444)
            lines.append("SSL_CERT_FILE=/run/mediaflow/receiver.pem")
        self.environment_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.environment_file.chmod(0o644)

    webhook_secret = "local-acceptance-webhook-secret"

    def compose_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "MEDIAFLOW_IMAGE": self.image,
                "MEDIAFLOW_CONFIG_FILE": str(self.config_file),
                "MEDIAFLOW_ENV_FILE": str(self.environment_file),
                "MEDIAFLOW_API_BIND": "127.0.0.1",
                "MEDIAFLOW_API_PORT": str(self.api_port),
                "MEDIAFLOW_UID": "10001",
                "MEDIAFLOW_GID": "10001",
            }
        )
        if self.media:
            # Set *before* startup, so the media stack is never confused with a
            # mount-change recreation of the media-free stack.
            environment["MEDIAFLOW_SOURCE_MEDIA_ROOT"] = str(self.source_root)
            environment["MEDIAFLOW_TARGET_MEDIA_ROOT"] = str(self.target_root)
        return environment

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.api_port}"

    def api(self, path: str, *, method: str = "GET", body: bytes | None = None):
        return http_request(f"{self.base}{path}", method=method, token=self.token, body=body)

    def json_api(self, path: str, *, method: str = "GET", body: object | None = None):
        payload = None if body is None else json.dumps(body).encode("utf-8")
        status, raw = self.api(path, method=method, body=payload)
        if status >= 400:
            raise RuntimeError(f"{method} {path} returned HTTP {status}: {raw.decode()[:600]}")
        return json.loads(raw)

    def up(self) -> None:
        run([*self.compose, "up", "-d", "--no-build"], environment=self.environment)

    def down(self) -> None:
        run(
            [*self.compose, "down", "-v", "--remove-orphans"],
            environment=self.environment,
            check=False,
        )
        shutil.rmtree(self.root, ignore_errors=True)

    def container_ids(self) -> dict[str, str]:
        names = run(
            [*self.compose, "ps", "--format", "json"],
            environment=self.environment,
        ).stdout
        by_service: dict[str, str] = {}
        for line in names.splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            by_service[record["Service"]] = record["ID"]
        if len(by_service) != len(ALL_SERVICES):
            raise RuntimeError(f"expected {len(ALL_SERVICES)} services, got {sorted(by_service)}")
        return by_service

    def process_ids(self) -> dict:
        code = (
            "import json; "
            "from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository; "
            "r=SQLiteTaskRepository('/data/mediaflow.sqlite3',read_only=True); "
            "print(json.dumps({x.service:x.instance_id for x in r.list_resident_services() "
            "if x.status.value!='stopped'}))"
        )
        result = run(
            [*self.compose, "exec", "-T", "api", "python", "-c", code], environment=self.environment
        )
        containers = self.container_ids()
        processes = {
            name: run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Pid}} {{.State.StartedAt}} {{.RestartCount}}",
                    identifier,
                ],
                environment=self.environment,
            ).stdout.strip()
            for name, identifier in containers.items()
        }
        return {
            "containers": containers,
            "processes": processes,
            "registrations": json.loads(result.stdout),
        }

    def wait_healthy(self) -> None:
        def healthy() -> bool:
            records = run(
                [*self.compose, "ps", "--format", "json"], environment=self.environment
            ).stdout
            state = {}
            for line in records.splitlines():
                if line.strip():
                    record = json.loads(line)
                    state[record["Service"]] = (record.get("State"), record.get("Health"))
            if set(state) != set(ALL_SERVICES):
                return False
            return all(
                running == "running" and health == "healthy" for running, health in state.values()
            )

        wait_until(healthy, timeout=READY_TIMEOUT_SECONDS, description="all services healthy")

    def wait_api(self) -> None:
        wait_until(
            lambda: http_request(f"{self.base}/health")[0] == 200,
            timeout=READY_TIMEOUT_SECONDS,
            description="API liveness",
        )

    def activate(self, document: dict) -> dict:
        """Create, fill, validate and activate the first Draft via the real API.

        Every step goes through the authenticated HTTP surface an operator
        actually uses, so this proves the journey rather than the internal
        service methods.
        """

        draft = self.json_api("/api/v1/configuration/drafts/first", method="POST", body={})
        saved = self.json_api(
            f"/api/v1/configuration/revisions/{draft['revisionId']}",
            method="PUT",
            body={"document": document, "expectedVersion": draft["version"]},
        )
        return self._validate_and_activate(saved["revisionId"])

    def successor(self, mutate) -> dict:
        """Publish a successor of the current Active through the real API.

        A published revision is immutable, so a later change is an explicit new
        Draft.  That is the supported A→B publication path the resident
        services must adopt without restarting.
        """

        status = self.json_api("/api/v1/configuration")
        active_id = status["active"]["revisionId"]
        detail = self.json_api(f"/api/v1/configuration/revisions/{active_id}")
        document = _bind_deployment_authority(detail["document"], self.database, self.token_env)
        mutate(document)
        imported = self.json_api(
            "/api/v1/configuration/drafts",
            method="POST",
            body={"document": document},
        )
        return self._validate_and_activate(imported["revisionId"])

    def _validate_and_activate(self, revision_id: str) -> dict:
        """Validate, run the applicable read-only evidence, then activate.

        Checked activation is the supported boundary, and it demands real
        read-only evidence for whatever the candidate actually declares.  The
        applicable checks are therefore run here rather than bypassed: an
        acceptance that skipped them would prove nothing about publication.
        """

        validated = self.json_api(
            f"/api/v1/configuration/revisions/{revision_id}/validate", method="POST", body={}
        )
        self.run_applicable_checks(revision_id, validated)
        return self.json_api(
            f"/api/v1/configuration/revisions/{revision_id}/activate",
            method="POST",
            body={"expectedVersion": validated["version"], "checked": True},
        )

    def run_applicable_checks(self, revision_id: str, validated: dict) -> None:
        """Run the read-only evidence the candidate actually declares.

        Applicability is derived from the candidate itself, exactly as the Slice
        requires: a declared enabled Storage needs read-only evidence, and an
        enabled ResourceLibrary needs its offline strategy test.  Nothing is
        fabricated, and an empty candidate needs no checks at all.
        """

        detail = self.json_api(f"/api/v1/configuration/revisions/{revision_id}")
        document = detail["document"]
        base = {
            "expectedVersion": validated["version"],
            "expectedDigest": validated["digest"],
        }
        for storage in document.get("storages", []):
            if not isinstance(storage, dict) or not storage.get("enabled", True):
                continue
            self.json_api(
                f"/api/v1/configuration/revisions/{revision_id}/storage-check",
                method="POST",
                body={**base, "storageId": storage["id"]},
            )
        for library in document.get("resourceLibraries", []):
            if not isinstance(library, dict) or not library.get("enabled", True):
                continue
            self.json_api(
                f"/api/v1/configuration/revisions/{revision_id}/recognition-strategy-test",
                method="POST",
                body={
                    **base,
                    "resourceLibraryId": library["id"],
                    "syntheticPath": "Acceptance.Movie.2025.mkv",
                    "liveMetadata": False,
                },
            )

        if document.get("classificationPolicies"):
            for recognition in document.get("recognitionTypes", []):
                self.json_api(
                    f"/api/v1/configuration/revisions/{revision_id}/destination-precheck",
                    method="POST",
                    body={
                        **base,
                        "recognitionType": recognition["id"],
                        "sample": {
                            "title": "Acceptance Movie",
                            "mediaType": "tv" if recognition["id"] == "B" else "movie",
                            "year": 2025,
                            "extension": "mkv",
                            "season": 1,
                            "episode": 1,
                            "genres": ["Action"],
                        },
                    },
                )

    token_env = "MEDIAFLOW_API_TOKEN"


def _bind_deployment_authority(document: dict, database: str, token_env: str) -> dict:
    """Re-bind the deployment authority a portable projection deliberately omits."""

    document["persistence"] = {"databasePath": database}
    document.setdefault("api", {})["principals"] = [
        {"id": "admin", "tokenEnv": token_env, "roles": ["admin"], "enabled": True}
    ]
    return document


def read_resident_state(stack: Stack) -> dict:
    """Read the durable resident presence rows out of the running stack.

    This reads the *running deployment's own* database rather than any host
    copy, so it proves the real containers registered themselves.
    """

    script = _RESIDENT_STATE_SCRIPT
    result = run(
        [
            *stack.compose,
            "exec",
            "-T",
            "api",
            "python",
            "-c",
            script,
        ],
        environment=stack.environment,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def empty_baseline_document(stack: Stack) -> dict:
    script = _EMPTY_BASELINE_SCRIPT
    result = run(
        [*stack.compose, "exec", "-T", "api", "python", "-c", script],
        environment=stack.environment,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def read_durable_counts(stack: Stack) -> dict:
    script = (
        "import json;"
        "from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository;"
        "repository=SQLiteTaskRepository('/data/mediaflow.sqlite3');"
        "print(json.dumps({"
        "'jobs':len(repository.list_jobs(limit=200)),"
        "'deliveries':len(repository.list_deliveries(limit=200)),"
        "'tasks':len(repository.list_tasks(limit=200))}))"
    )
    result = run(
        [*stack.compose, "exec", "-T", "api", "python", "-c", script],
        environment=stack.environment,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def assert_no_media_mount(stack: Stack) -> None:
    result = run(
        ["docker", "compose", "-f", str(ROOT / "compose.yaml"), "config", "--format", "json"],
        environment=stack.environment,
    )
    document = json.loads(result.stdout)
    for name, definition in document["services"].items():
        targets = {item["target"] for item in definition["volumes"]}
        if "/media/incoming" in targets or "/media/organized" in targets:
            raise RuntimeError(f"default Compose still declares a media mount for {name}")
    if stack.token in result.stdout:
        raise RuntimeError("rendered Compose output contains the deployment API token")


#: Services whose work genuinely depends on business configuration, and which
#: therefore must report *why* they are idle before first activation.  The
#: Worker is deliberately excluded: with no configuration it is not blocked, it
#: simply has nothing to consume, and it stays ready for whatever an operator
#: admits later.
CONFIGURATION_DEPENDENT_SERVICES = ("scheduler", "notification-worker")


def assert_waiting(stack: Stack, *, services: tuple[str, ...]) -> None:
    """A waiting service is infrastructure-ready and says why it is idle."""

    state = read_resident_state(stack)
    for service in services:
        entry = state["services"][service]
        if not entry["ready"]:
            raise RuntimeError(
                f"{service} is not infrastructure-ready while waiting: {entry['condition']}"
            )
        if not entry["waiting"]:
            raise RuntimeError(
                f"{service} reports no waiting reason during empty setup, so an operator "
                "would see an idle process with no explanation"
            )
        if not entry["waitingReason"]:
            raise RuntimeError(f"{service} waits without naming a bounded reason")


def assert_real_web_status(stack: Stack) -> None:
    code = """
        import {chromium, expect} from '@playwright/test';
        const browser = await chromium.launch({headless:true});
        try {
            const page = await browser.newPage({viewport:{width:390,height:844}});
            await page.goto(process.env.MF_TEST_BASE + '/ui-v2/operations');
            await page.getByLabel('API token').fill(process.env.MF_TEST_TOKEN);
            const response = page.waitForResponse(
                r => r.url().endsWith('/api/v1/management/readiness'));
            await page.getByRole('button', {name:'Connect', exact:true}).click();
            if ((await response).status() !== 200) throw new Error('readiness request failed');
            const region = page.getByRole('region', {name:'常驻服务状态'});
            await expect(region).toContainText('notification-worker');
            await expect(region).toContainText('基础设施就绪');
            await expect(region).toContainText('等待业务配置');
            await expect(region.getByRole('link', {name:'前往系统设置'})).toBeVisible();
            const stores = await page.evaluate(
                () => JSON.stringify([localStorage, sessionStorage]));
            if(stores.includes(process.env.MF_TEST_TOKEN)) throw new Error('token persisted');
        } finally { await browser.close(); }
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        cwd=ROOT / "web",
        env={**os.environ, "MF_TEST_BASE": stack.base, "MF_TEST_TOKEN": stack.token},
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("real Python-served browser status failed: " + result.stderr)
    print("   real Python-served Web renders service health, waiting and Settings recovery")


def accept_media_free_stack(image: str, receiver: WebhookReceiver, keep: bool) -> None:
    suffix = f"{os.getpid()}-{int(time.time())}"
    # The receiver address and its certificate must both be settled *before*
    # the stack is rendered, because the certificate is copied into the stack
    # directory and bind-mounted.  Resolving them later would leave every
    # container holding the initial certificate.
    webhook_url = receiver.url
    stack = Stack(f"{PROJECT_PREFIX}-{suffix}", image, media=False, receiver=receiver)
    try:
        print("== media-free default stack ==")
        assert_no_media_mount(stack)
        print("   building image...")
        run(
            [
                "docker",
                "build",
                "--file",
                str(ROOT / "Dockerfile"),
                "--tag",
                image,
                str(ROOT),
            ],
            environment=stack.environment,
        )
        print("   starting with no media mount at all...")
        stack.up()
        stack.wait_healthy()
        stack.wait_api()
        print("   all four services healthy without a media mount")

        readiness = stack.json_api("/api/v1/management/readiness")
        if readiness["runtimeConfigured"]:
            raise RuntimeError("a fresh media-free deployment reported a configured runtime")
        if readiness["managementReady"] is not True:
            raise RuntimeError("management is not ready on a fresh deployment")
        services = readiness["infrastructure"]["services"]
        for name in RESIDENT_SERVICES:
            if not services[name]["ready"]:
                raise RuntimeError(f"{name} did not report infrastructure readiness")
        print("   resident services registered and infrastructure-ready")

        assert_waiting(stack, services=CONFIGURATION_DEPENDENT_SERVICES)
        print("   Scheduler and Notification Worker wait with a bounded reason")
        assert_real_web_status(stack)

        before = read_durable_counts(stack)
        if before != {"jobs": 0, "deliveries": 0, "tasks": 0}:
            raise RuntimeError(f"startup created durable work: {before}")

        print("   activating an empty baseline through the real API...")
        baseline = empty_baseline_document(stack)
        stack.activate(baseline)
        status = stack.json_api("/api/v1/configuration")
        if not status["emptyActive"]:
            raise RuntimeError("empty baseline activation did not publish an empty Active")
        if "配置已激活，媒体业务尚未配置" not in (status.get("nextAction") or ""):
            raise RuntimeError(f"empty activation message is wrong: {status.get('nextAction')}")
        after_activation = read_durable_counts(stack)
        if after_activation != {"jobs": 0, "deliveries": 0, "tasks": 0}:
            raise RuntimeError(f"empty activation created durable work: {after_activation}")
        print("   empty Active published; no media work, delivery or mutation started")

        identities = stack.process_ids()
        print("   publishing an eligible schedule + webhook without restarting...")
        receiver.received.clear()

        def configure(document: dict) -> None:
            document.setdefault("notifications", {})["webhooks"] = [
                {
                    "id": "primary",
                    "url": webhook_url,
                    "secretEnv": "MEDIAFLOW_WEBHOOK_SECRET",
                    "events": ["schedule.emitted", "job.completed", "job.failed"],
                    "enabled": True,
                }
            ]
            document.setdefault("automation", {})["schedules"] = [
                {
                    "id": "acceptance-scan",
                    "command": "preview",
                    "intervalSeconds": 2,
                    "enabled": True,
                }
            ]

        stack.successor(configure)

        wait_until(
            lambda: bool(receiver.received),
            timeout=120.0,
            description="a signed webhook delivery from the resident Notification Worker",
        )
        after_publication = stack.process_ids()
        if after_publication != identities:
            raise RuntimeError(
                f"configuration publication replaced containers: {identities} -> "
                f"{after_publication}"
            )
        print("   resident process identities unchanged across publication")

        signed = receiver.received[0]
        if not signed["signature"].startswith("sha256="):
            raise RuntimeError(f"delivery was not signed: {signed['signature']!r}")
        if signed["event"] != "schedule.emitted":
            raise RuntimeError(f"unexpected delivery event {signed['event']!r}")
        print(f"   signed {signed['event']} delivery reached the controlled receiver")

        # A real 503 creates a durable retry through the production transport.
        receiver.response_status = 503
        retries = []

        def has_retry():
            retries[:] = stack.json_api("/api/v1/notifications?status=retry")["items"]
            return bool(retries)

        wait_until(has_retry, timeout=90, description="real transport retry")
        saved = retries[0]
        stack.successor(
            lambda document: document["notifications"]["webhooks"][0].update(
                url=webhook_url.replace("/hook", "/replacement")
            )
        )
        receiver.response_status = 200
        time.sleep(12)
        current = stack.json_api("/api/v1/notifications/" + saved["deliveryId"])
        if current["status"] != "retry" or current["retrySafe"] is not False:
            raise RuntimeError("changed target did not preserve its blocked durable retry")
        if any(
            item["eventId"] == saved["eventId"] and item["path"] == "/replacement"
            for item in receiver.received
        ):
            raise RuntimeError("old event was silently sent to the replacement recipient")
        stack.successor(
            lambda document: document["notifications"]["webhooks"][0].update(url=webhook_url)
        )
        wait_until(
            lambda: (
                stack.json_api("/api/v1/notifications/" + saved["deliveryId"])["status"]
                == "delivered"
            ),
            timeout=90,
            description="restored original recipient recovery",
        )
        print(
            "   old retry stayed blocked after URL change and recovered only at its original target"
        )
        final_identities = stack.process_ids()
        if final_identities != identities:
            raise RuntimeError("a resident process restarted across target publication/recovery")
        print("   process identities before: " + json.dumps(identities, sort_keys=True))
        print("   process identities after: " + json.dumps(final_identities, sort_keys=True))

        counts = read_durable_counts(stack)
        if counts["jobs"] < 1:
            raise RuntimeError("the eligible schedule emitted no durable Job")
        if counts["deliveries"] < 1:
            raise RuntimeError("the eligible schedule produced no durable delivery")
        print(f"   durable work produced without restart: {counts}")

        state = read_resident_state(stack)
        scheduler = state["services"]["scheduler"]
        if scheduler["waiting"]:
            raise RuntimeError(
                "Scheduler is still waiting after a valid publication: "
                f"{scheduler['waitingReason']}"
            )
        print("   Scheduler reported working again after the valid publication")
        print("== media-free default stack PASSED ==")
    finally:
        if not keep:
            stack.down()
        else:
            print(f"   keeping stack {stack.name} for inspection")


def wait_job(stack: Stack, admitted: dict) -> None:
    identifier = admitted.get("job_id") or admitted.get("jobId")

    def complete():
        current = stack.json_api(f"/api/v1/jobs/{identifier}")
        status = current["status"]
        if status in {"failed", "cancelled"}:
            raise RuntimeError(f"admitted {current.get('command')} failed: {current}")
        return status == "completed"

    wait_until(complete, timeout=120, description="resident Job completion")


def complete_transfer(
    stack: Stack, kind: str, source: str, destination: str, path: str, destination_field: str
) -> None:
    prefix = f"/api/v1/{kind}/{source}/files"
    query = urllib.parse.urlencode(
        {"path": path, "to": destination, "toPath": "", "operation": "copy", "conflict": "fail"}
    )
    impact = stack.json_api(prefix + "/transfer-impact?" + query)
    admitted = stack.json_api(
        prefix + "/transfers",
        method="POST",
        body={
            "operation": "copy",
            "paths": [path],
            destination_field: destination,
            "destinationDirectory": "",
            "conflictMode": "fail",
            "manifestDigest": impact["manifestDigest"],
        },
    )

    def complete():
        current = stack.json_api(prefix + "/transfers/" + admitted["taskId"])
        if current.get("terminal") and current["status"] != "SUCCESS":
            raise RuntimeError(f"isolated transfer failed: {current}")
        return current["status"] == "SUCCESS"

    wait_until(complete, timeout=120, description=kind + " resident Copy completion")


def accept_media_stack(image: str, keep: bool, receiver: WebhookReceiver) -> None:
    """A separate stack proves real media work with mounts present before start."""

    suffix = f"{os.getpid()}-{int(time.time())}"
    proxy = LocalMetadataProxy(receiver)
    stack = Stack(f"{PROJECT_PREFIX}-media-{suffix}", image, media=True, receiver=receiver)
    with stack.environment_file.open("a") as stream:
        stream.write(
            f"TMDB_ACCESS_TOKEN=fake-local-metadata\n"
            f"HTTPS_PROXY=http://{receiver._reachable_host}:{proxy.server.server_port}\n"
            "NO_PROXY=localhost,127.0.0.1\n"
        )
    try:
        print("== optional media-mount stack ==")
        result = run(
            [
                "docker",
                "compose",
                "-f",
                str(ROOT / "compose.yaml"),
                "-f",
                str(ROOT / "compose.media-mounts.yaml"),
                "config",
                "--format",
                "json",
            ],
            environment=stack.environment,
        )
        document = json.loads(result.stdout)
        targets = {item["target"] for item in document["services"]["worker"]["volumes"]}
        if not {"/media/incoming", "/media/organized"} <= targets:
            raise RuntimeError("the media overlay did not add both confined mounts")
        print("   media overlay adds both confined mounts")

        stack.up()
        stack.wait_healthy()
        stack.wait_api()
        identities = stack.process_ids()
        stack.activate(empty_baseline_document(stack))
        status = stack.json_api("/api/v1/configuration")
        if not status["emptyActive"]:
            raise RuntimeError("media stack did not reach a valid empty Active")
        print("   media stack reached an empty Active with mounts present")

        # An empty Active has no ResourceLibrary, so a Scan is correctly refused.
        # The point of this stack is that a *populated* Active reaches real
        # media through the optional mounts, so the library is configured here.
        source_file = stack.source_root / "movies" / "Acceptance.Movie.2025.mkv"
        source_file.parent.mkdir(exist_ok=True)
        source_file.write_bytes(b"not-real-media")

        def configure_library(document: dict) -> None:
            full = make_deployment_configuration()
            full["api"] = document["api"]
            full["api"]["remoteExecution"] = {"enabled": True, "maximumTtlSeconds": 900}
            full["recognitionRules"] = [
                {
                    "id": "acceptance",
                    "name": "Acceptance",
                    "priority": 100,
                    "score": 100,
                    "stopOnMatch": True,
                    "condition": {"field": "extension", "operator": "equals", "value": "mkv"},
                    "outputRecognitionType": "A",
                }
            ]
            full["resourceLibraries"][0]["extensions"] = ["mkv"]
            full["resourceLibraries"].append(
                {
                    "id": "resource-destination",
                    "name": "Resource destination",
                    "storageId": "media-target",
                    "storagePath": "resource-copies",
                    "enabled": True,
                }
            )
            full["mediaLibraries"].append(
                {
                    "id": "media-destination",
                    "name": "Media destination",
                    "storageId": "media-target",
                    "rootPath": "media-copies",
                }
            )
            for policy in full["organizePolicies"]:
                policy["operation"] = "COPY"
            document.clear()
            document.update(full)

        (stack.target_root / "resource-copies").mkdir()
        (stack.target_root / "media-copies").mkdir()
        (stack.target_root / "Movies").mkdir()
        (stack.target_root / "TV Shows").mkdir()
        for directory in stack.target_root.iterdir():
            directory.chmod(0o777)
        stack.successor(configure_library)
        print("   published a ResourceLibrary over the confined media mount")

        before = stack.container_ids()
        stack.json_api("/api/v1/configuration")
        if stack.container_ids() != before:
            raise RuntimeError("reading configuration state replaced the media containers")
        print("   reading configuration state recreated no container")

        # The real Local Storage proof runs through the *resident Worker*, which
        # is the boundary this Task owns: a ResourceLibrary transfer admitted
        # against the published Active must be consumed by an already-running
        # Worker with no restart and no mount change.
        source_file = stack.source_root / "movies" / "Acceptance.Movie.2025.mkv"
        source_file.parent.mkdir(exist_ok=True)
        source_file.write_bytes(b"not-real-media")
        status = stack.json_api("/api/v1/configuration")
        if not status.get("runtimeConfigured"):
            raise RuntimeError("the populated library configuration is not runtime-configured")
        capabilities = status.get("capabilities", {})
        storage = capabilities.get("storage", {})
        library = capabilities.get("resourceLibrary", {})
        if storage.get("state") != "CONFIGURED":
            raise RuntimeError(f"the published Storage is not reported as configured: {storage}")
        if library.get("state") != "CONFIGURED":
            raise RuntimeError(
                f"the published ResourceLibrary is not reported as configured: {library}"
            )
        print("   populated Active reports Storage and ResourceLibrary as configured")

        wait_until(
            lambda: (
                stack.json_api("/api/v1/workers/readiness")
                .get("workReadiness", {})
                .get("resourceFilesTransfer", {})
                .get("ready")
                is True
            ),
            timeout=90.0,
            description="the resident Worker reporting transfer readiness",
        )
        print("   resident Worker reports ResourceLibrary transfer readiness")
        for command in ("scan", "preview"):
            admitted = stack.json_api("/api/v1/jobs", method="POST", body={"command": command})
            wait_job(stack, admitted)
        if list(stack.target_root.rglob("*.mkv")):
            raise RuntimeError("Scan/Preview mutated the isolated destination")
        issued = run(
            [
                *stack.compose,
                "exec",
                "-T",
                "api",
                "mediaflow",
                "--config",
                "/config/mediaflow.json",
                "execution-authorizations",
                "issue",
                "--ttl-seconds",
                "300",
                "--max-items",
                "1",
                "--actor",
                "isolated-acceptance",
            ],
            environment=stack.environment,
        )
        ticket = next(
            line.removeprefix("Token: ")
            for line in issued.stdout.splitlines()
            if line.startswith("Token: ")
        )
        request = urllib.request.Request(
            stack.base + "/api/v1/jobs",
            data=json.dumps({"command": "organize", "execute": True, "limit": 1}).encode(),
            headers={
                "Authorization": "Bearer " + stack.token,
                "X-MediaFlow-Execution-Token": ticket,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            admitted = json.load(response)
        wait_job(stack, admitted)
        organized = list((stack.target_root / "Movies").rglob("*.mkv"))
        if len(organized) != 1 or organized[0].read_bytes() != source_file.read_bytes():
            raise RuntimeError(
                "Organize did not produce exactly the authorized file copy: "
                + json.dumps(stack.json_api("/api/v1/tasks"))
                + " files="
                + str(list(stack.target_root.rglob("*")))
            )
        if not proxy.requests:
            raise RuntimeError("production TMDB client did not reach the controlled TLS fixture")
        complete_transfer(
            stack,
            "resource-libraries",
            "source",
            "resource-destination",
            source_file.relative_to(stack.source_root).as_posix(),
            "destinationResourceLibraryId",
        )
        complete_transfer(
            stack,
            "media-libraries",
            "movies",
            "media-destination",
            organized[0].relative_to(stack.target_root / "Movies").as_posix(),
            "destinationMediaLibraryId",
        )
        if not list((stack.target_root / "resource-copies").rglob("*.mkv")):
            raise RuntimeError("ResourceLibrary Copy produced no destination file")
        if not list((stack.target_root / "media-copies").rglob("*.mkv")):
            raise RuntimeError("MediaLibrary Copy produced no destination file")
        final_identities = stack.process_ids()
        if identities != final_identities:
            raise RuntimeError("a resident process restarted across setup/publication/work")
        print("   process identities before: " + json.dumps(identities, sort_keys=True))
        print("   process identities after: " + json.dumps(final_identities, sort_keys=True))
        print(
            "   Scan, Preview, Organize and both library Copy operations completed; same processes"
        )

        print("== optional media-mount stack PASSED ==")
    finally:
        proxy.stop()
        if not keep:
            stack.down()
        else:
            print(f"   keeping stack {stack.name} for inspection")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=IMAGE_TAG)
    parser.add_argument("--keep", action="store_true", help="keep containers for inspection")
    arguments = parser.parse_args()
    if shutil.which("docker") is None:
        print("Docker engine is unavailable; empty-baseline acceptance SKIP")
        return 0
    if shutil.which("openssl") is None:
        print("openssl is unavailable; the signed-delivery step cannot run; SKIP")
        return 0
    receiver = WebhookReceiver()
    receiver.start()
    try:
        accept_media_free_stack(arguments.image, receiver, arguments.keep)
        accept_media_stack(arguments.image, arguments.keep, receiver)
    finally:
        receiver.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
