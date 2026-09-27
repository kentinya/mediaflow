"""Task 40.3 correction: real processes, durable pins and read-only probes."""

from __future__ import annotations

import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from mediaflow.application.notification import NotificationPublisher, NotificationWorker
from mediaflow.container_probe import resident_service_readiness_error
from mediaflow.domain.notification import NotificationEvent, NotificationEventType
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from tests.test_notifications import FakeTransport, webhook
from tests.test_resident_services import ResidentDeploymentFixture


class ResidentCorrectionTests(ResidentDeploymentFixture):
    def wait_for(self, predicate, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.1)
        self.fail("resident state did not converge")

    def start(self, service):
        log = self.root / f"{service}.log"
        stream = log.open("w+")
        self.addCleanup(stream.close)
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from mediaflow.cli import main; raise SystemExit(main())",
                "--config",
                str(self.config),
                service,
                "run",
                "--poll-seconds",
                "0.1",
            ],
            stdout=stream,
            stderr=stream,
        )

        def stop():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

        self.addCleanup(stop)

        def registered():
            self.assertIsNone(process.poll(), log.read_text())
            with SQLiteTaskRepository(self.database, read_only=True) as repo:
                return any(
                    row.service == service
                    and repo.get_resident_service_wait_state(
                        service, row.instance_id
                    ).waiting_reason
                    == "unconfigured"
                    for row in repo.list_resident_services()
                )

        self.wait_for(registered)
        return process

    def test_three_processes_survive_real_write_lock_and_resume_heartbeats(self):
        with SQLiteTaskRepository(self.database):
            pass
        processes = [
            self.start(service) for service in ("worker", "scheduler", "notification-worker")
        ]
        with sqlite3.connect(self.database) as lock:
            lock.execute("BEGIN IMMEDIATE")
            time.sleep(7)
            self.assertTrue(
                all(process.poll() is None for process in processes),
                "\n".join(path.read_text() for path in self.root.glob("*.log")),
            )
            lock.rollback()
        released = datetime.now(UTC)

        def recovered():
            self.assertTrue(
                all(process.poll() is None for process in processes),
                "\n".join(path.read_text() for path in self.root.glob("*.log")),
            )
            with SQLiteTaskRepository(self.database, read_only=True) as repo:
                return all(
                    row.last_heartbeat_at > released
                    and repo.get_resident_service_wait_state(
                        row.service, row.instance_id
                    ).waiting_reason
                    == "unconfigured"
                    for row in repo.list_resident_services()
                )

        self.wait_for(recovered)
        with SQLiteTaskRepository(self.database, read_only=True) as repo:
            state = repo.list_resident_services()
            for row in state:
                waiting = repo.get_resident_service_wait_state(row.service, row.instance_id)
                self.assertEqual(waiting.waiting_reason, "unconfigured")

    def test_live_worker_consumes_later_and_old_published_scan_pins(self):
        with SQLiteTaskRepository(self.database):
            pass
        process = self.start("worker")
        self.publish_first_draft(self.empty_baseline())
        source = self.root / "source"
        source.mkdir()

        def configure(document):
            document["storages"] = [
                {
                    "id": "local",
                    "type": "local",
                    "name": "Local",
                    "rootPath": str(source),
                    "readOnly": True,
                }
            ]
            document["resourceLibraries"] = [
                {
                    "id": "source",
                    "name": "Source",
                    "storageId": "local",
                    "storagePath": "",
                    "displayRootPath": str(source),
                    "enabled": True,
                }
            ]

        revision_a = self.publish_successor(configure)
        process.send_signal(signal.SIGSTOP)
        try:
            code, out, err = self.cli("jobs", "submit", "scan")
            self.assertEqual(code, 0, err)
            self.publish_successor(
                lambda document: document["resourceLibraries"][0].update(name="B")
            )
            code, out, err = self.cli("jobs", "submit", "scan")
            self.assertEqual(code, 0, err)
            with SQLiteTaskRepository(self.database, read_only=True) as repo:
                self.assertEqual([job.status.value for job in repo.list_jobs()], ["pending"] * 2)
        finally:
            process.send_signal(signal.SIGCONT)

        def completed():
            self.assertIsNone(process.poll())
            with SQLiteTaskRepository(self.database, read_only=True) as repo:
                jobs = repo.list_jobs()
                return len(jobs) == 2 and all(job.status.value == "completed" for job in jobs)

        self.wait_for(completed)
        with SQLiteTaskRepository(self.database, read_only=True) as repo:
            pins = {job.configuration_snapshot_id for job in repo.list_jobs()}
            self.assertIn(revision_a, pins)
            self.assertEqual(len(pins), 2)

    def test_changed_recipient_does_not_claim_pending_or_retry_after_restart(self):
        now = datetime.now(UTC)
        original = webhook()
        self.publish_first_draft(self.empty_baseline())
        self.publish_successor(
            lambda document: document["notifications"].update(webhooks=[original.document()])
        )
        from mediaflow.final_cli import _resolve_resident_configuration

        environment = patch.dict(os.environ, {original.secret_env: "fake"})
        environment.start()
        self.addCleanup(environment.stop)

        def targets():
            return _resolve_resident_configuration(str(self.config)).resolve_webhook_targets()

        with SQLiteTaskRepository(self.database) as repo:
            for index, status in enumerate(("pending", "retry")):
                event = NotificationEvent(
                    str(index), NotificationEventType.JOB_COMPLETED, now, {"jobId": str(index)}
                )
                delivery = NotificationPublisher(repo, (original,)).publish(event)[0]
                if status == "retry":
                    worker = NotificationWorker(
                        repo, {"ops": (original, "fake")}, FakeTransport(503), clock=lambda: now
                    )
                    # First pending event also stays independent of the second.
                    worker.run_next()
        self.publish_successor(
            lambda document: document["notifications"]["webhooks"][0].update(
                url="https://replacement.invalid/hook"
            )
        )
        with SQLiteTaskRepository(self.database) as repo:
            before = repo.list_deliveries()
            transport = FakeTransport()
            worker = NotificationWorker(
                repo,
                targets,
                transport,
                clock=lambda: now + timedelta(hours=1),
            )
            self.assertIsNone(worker.run_next())
            self.assertEqual(repo.list_deliveries(), before)
            self.assertEqual(transport.requests, [])
            self.publish_successor(
                lambda document: document["notifications"]["webhooks"][0].update(url=original.url)
            )
            restored = NotificationWorker(
                repo,
                targets,
                FakeTransport(),
                clock=lambda: now + timedelta(hours=1),
            )
            self.assertEqual(restored.run_next().status.value, "delivered")
            self.assertEqual(
                repo.get_delivery(delivery.delivery_id).target_digest, original.target_digest
            )

    def test_read_only_probe_never_creates_database_or_installs_tables(self):
        environment = {"MEDIAFLOW_CONFIG": str(self.config), "MF_ADMIN_TOKEN": "fake"}
        self.assertIsNotNone(resident_service_readiness_error("scheduler", environ=environment))
        self.assertFalse(self.data.joinpath("mediaflow.sqlite3").exists())
        base = self.root / "task-base"
        base.mkdir()
        archive = subprocess.run(
            ["git", "archive", "360e59e0791c60635f050a0444b1a2d0b4458ea4"],
            check=True,
            capture_output=True,
        )
        subprocess.run(["tar", "-x", "-C", str(base)], input=archive.stdout, check=True)
        subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; "
                "from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository; "
                "r=SQLiteTaskRepository(sys.argv[1]); assert r.schema_version==38; r.close()",
                self.database,
            ],
            cwd=base,
            env={**os.environ, "PYTHONPATH": str(base)},
            check=True,
        )
        before = self.data.joinpath("mediaflow.sqlite3").read_bytes()
        self.assertIsNotNone(resident_service_readiness_error("scheduler", environ=environment))
        self.assertEqual(self.data.joinpath("mediaflow.sqlite3").read_bytes(), before)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE name IN "
                    "('resident_services','resident_service_wait_state')"
                ).fetchall(),
                [],
            )
        # Explicit initialization is the migration boundary; the probe itself
        # above cannot install schema, create a DB or advance its version.
        with SQLiteTaskRepository(self.database) as migrated:
            self.assertEqual(migrated.schema_version, 39)
            self.assertEqual(migrated.list_resident_services(), ())
