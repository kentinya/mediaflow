#!/usr/bin/env python3
"""Real-Python browser proof for the Notification workspace cards.

The proof starts the production-shaped Python API in-process over temporary
SQLite repositories and temporary Local roots. A recordable fake Webhook
transport replaces the outbound HTTPS client, so the explicit signed test can
be counted without any network, production credential or receiver. A second
transport seeds one real dead-letter delivery through the real Notification
Worker.

The browser then drives the current built V2 artifact through the real
Notification journey:

* the list is the persistent background of the definition card;
* opening and reading the card sends no test request and changes no
  configuration;
* one explicit signed test sends exactly one request and creates no delivery;
* the editor saves a real Draft revision, validates it and publishes only the
  selected Webhook change;
* the filtered delivery list opens one delivery card, requeues exactly the
  selected dead-letter row and returns to the same filter;
* secrets, tokens, digests and delivery bodies stay out of rendered content.

No production service, credential, user media or external network is used.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "notification-proof-throwaway-token"
WEBHOOK_ID = "proof-webhook"
SECRET_ENV = "MEDIAFLOW_WEBHOOK_PROOF_SECRET"
SECRET_VALUE = "notification-proof-secret-value"
DRAFT_WEBHOOK_URL = "https://example.invalid/hooks/proof"
EDITED_WEBHOOK_URL = "https://example.invalid/hooks/proof-edited"
DELIVERY_EVENT_ID = "proof-task-completed"


class RecordingTransport:
    """A deterministic Webhook transport that records only request metadata."""

    def __init__(self, status: int = 204) -> None:
        self.status = status
        self.requests: list[object] = []

    def send(self, request) -> int:
        self.requests.append(request)
        return self.status


class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class QuietRequestHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


def free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(base: str, path: str, method: str = "GET") -> dict:
    request = urllib.request.Request(
        base + path,
        method=method,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def wait_for_health(base: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(base + "/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    raise RuntimeError("Python API did not become healthy")


def active_document(configuration) -> dict:
    active = configuration.active()
    if active is None:
        raise RuntimeError("proof configuration has no Active revision")
    return copy.deepcopy(active.document)


def webhooks_from(document: dict) -> list[dict]:
    section = document.get("webhooks")
    if not isinstance(section, list):
        section = document.get("notifications", {}).get("webhooks", [])
    return section


def build_configuration(root: Path) -> dict:
    value = json.loads((ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8"))
    value["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    value["historyPath"] = str(root / "history.jsonl")
    for item in value.get("notifications", {}).get("webhooks", []):
        item.update(
            {
                "id": WEBHOOK_ID,
                "url": DRAFT_WEBHOOK_URL,
                "secretEnv": SECRET_ENV,
                "events": ["task.completed", "task.failed"],
                "enabled": True,
                "timeoutSeconds": 10,
                "maxAttempts": 1,
                "baseRetrySeconds": 1,
                "maxRetrySeconds": 2,
            }
        )
    return value


def start_api(root: Path):
    from mediaflow.application.configuration_snapshot import ManagedConfigurationService
    from mediaflow.application.notification import NotificationPublisher, NotificationWorker
    from mediaflow.domain.notification import (
        NotificationEvent,
        NotificationEventType,
        WebhookDefinition,
    )
    from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
    from mediaflow.infrastructure.sqlite_configuration_management import (
        SQLiteConfigurationRepository,
    )
    from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
    from mediaflow.interfaces.service_api import MediaFlowApi

    os.environ[SECRET_ENV] = SECRET_VALUE
    os.environ["MEDIAFLOW_UI_V2_ASSET_ROOT"] = str(ROOT / "web" / "dist")

    document = build_configuration(root)
    configuration_repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
    configuration = ManagedConfigurationService(
        configuration_repository,
        bootstrap_database_path=str(root / "runtime.sqlite3"),
    )
    draft = configuration.import_draft(document, actor="notification-proof")
    validated = configuration.validate(draft.revision_id, actor="notification-proof")
    configuration.activate(
        validated.revision_id,
        expected_version=validated.version,
        actor="notification-proof",
    )
    repository = SQLiteTaskRepository(str(root / "runtime.sqlite3"))

    admin = ResolvedApiPrincipal(TOKEN, TOKEN, frozenset(ApiPermission))
    transport = RecordingTransport(204)
    api = MediaFlowApi(
        repository,
        None,
        principals=(admin,),
        configuration_service=configuration,
        bootstrap_document=document,
        webhook_transport=transport,
    )

    # Seed one durable dead-letter delivery through the real publisher/worker.
    runtime = configuration._load_for_runtime(configuration.active().document)
    definition = next(item for item in runtime.webhooks if item.webhook_id == WEBHOOK_ID)
    event = NotificationEvent(
        DELIVERY_EVENT_ID,
        NotificationEventType.JOB_COMPLETED,
        datetime.now(UTC),
        {"jobId": DELIVERY_EVENT_ID},
    )
    created = NotificationPublisher(repository, (definition,)).publish(event)
    if not created:
        raise RuntimeError("proof delivery was not created")
    delivery_id = created[0].delivery_id
    dead_letter_transport = RecordingTransport(400)
    worker_definition = WebhookDefinition(
        definition.webhook_id,
        definition.url,
        definition.secret_env,
        definition.events,
        enabled=True,
        timeout_seconds=definition.timeout_seconds,
        max_attempts=1,
        base_retry_seconds=1,
        max_retry_seconds=2,
    )
    worker = NotificationWorker(
        repository,
        {WEBHOOK_ID: (worker_definition, SECRET_VALUE)},
        dead_letter_transport,
    )
    settled = worker.run_next()
    if settled is None or settled.status.value != "dead-letter":
        raise RuntimeError("proof delivery did not reach dead-letter")
    if len(dead_letter_transport.requests) != 1:
        raise RuntimeError("proof worker did not perform one bounded request")

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    server = ThreadedWSGIServer(("127.0.0.1", port), QuietRequestHandler)
    server.set_app(api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    state = {
        "base": base,
        "server": server,
        "thread": thread,
        "transport": transport,
        "delivery_id": delivery_id,
        "delivery_repository": repository,
        "configuration": configuration,
        "configuration_repository": configuration_repository,
        "before_document": active_document(configuration),
    }
    return state


def stop_api(state: dict) -> None:
    state["server"].shutdown()
    state["server"].server_close()
    state["thread"].join(timeout=5)
    state["delivery_repository"].close()
    state["configuration_repository"].close()


READ_ONLY_BROWSER = r"""
import { chromium, expect } from '@playwright/test';

const base = process.env.MF_PROOF_BASE;
const token = process.env.MF_PROOF_TOKEN;
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(base + '/ui-v2/operations/notifications');
  await page.getByLabel('API token').fill(token);
  await page.getByRole('button', { name: 'Connect' }).click();
  await expect(page.getByRole('heading', { name: '通知', exact: true })).toBeVisible();
  await page.getByRole('link', { name: '查看定义' }).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '关闭', exact: true })
    .click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('link', { name: '查看投递记录' }).click();
  await expect(page.getByRole('heading', { name: '通知投递记录', exact: true })).toBeVisible();
  await page.getByRole('link', { name: '查看投递' }).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '关闭', exact: true })
    .click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  console.log(JSON.stringify({ readOnly: true }));
} finally {
  await browser.close();
}
"""

BROWSER = r"""
import { chromium, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.MF_PROOF_BASE;
const token = process.env.MF_PROOF_TOKEN;
const secret = process.env.MF_PROOF_SECRET;
const artifacts = process.env.MF_PROOF_ARTIFACTS;
const deliveryId = process.env.MF_PROOF_DELIVERY_ID;
const webhookId = process.env.MF_PROOF_WEBHOOK_ID;

async function shot(page, name) {
  // Let the shared card enter animation settle so the review image shows the
  // final opaque card, not an intermediate frame.
  await page.waitForTimeout(320);
  const target = path.join(artifacts, `${name}.png`);
  await page.screenshot({ path: target, fullPage: false });
  return path.basename(target);
}

const browser = await chromium.launch({ headless: true });
const screenshots = [];
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(base + '/ui-v2/operations/notifications');
  await page.getByLabel('API token').fill(token);
  await page.getByRole('button', { name: 'Connect' }).click();
  await expect(page.getByRole('heading', { name: '通知', exact: true })).toBeVisible();
  await expect(page.getByText('已生效', { exact: true })).toBeVisible();
  await expect(page.getByText('密钥引用：已就绪', { exact: true })).toBeVisible();
  screenshots.push(await shot(page, 'definitions-list-desktop'));

  await page.getByRole('link', { name: '查看定义' }).first().click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(page.getByRole('heading', { name: '通知', exact: true })).toBeVisible();
  await expect(dialog.getByText('密钥引用：已就绪', { exact: true })).toBeVisible();
  screenshots.push(await shot(page, 'definition-card-desktop'));

  await dialog.getByRole('button', { name: '发送签名测试' }).click();
  await expect(dialog.getByText(/测试成功/)).toBeVisible();
  await dialog.getByRole('button', { name: '关闭', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);

  await page.getByRole('button', { name: '创建后继草稿' }).click();
  await expect(page.getByText(/草稿 · 版本/)).toBeVisible();
  await page.getByRole('link', { name: '查看定义' }).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: '编辑草稿' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(
    page.getByRole('dialog').getByRole('heading', { name: `编辑 Webhook ${webhookId}` }),
  ).toBeVisible();

  await page.getByLabel('HTTPS 接收地址').fill('https://example.invalid/hooks/proof-edited');
  await page.setViewportSize({ width: 390, height: 844 });
  screenshots.push(await shot(page, 'editor-card-390'));
  await page.getByRole('button', { name: '保存到草稿', exact: true }).click();
  await expect(page.getByText(/已保存到草稿版本/)).toBeVisible();
  await page.getByRole('button', { name: '检查草稿', exact: true }).click();
  await expect(page.getByRole('heading', { name: '草稿检查通过' })).toBeVisible();
  await page
    .getByLabel('我确认把当前已检查的草稿发布为新的已生效配置')
    .check();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: '发布已检查草稿', exact: true }).click();
  await expect(page.getByText(/草稿已发布为已生效配置/)).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);

  await page.getByRole('link', { name: '查看投递记录' }).click();
  await expect(page.getByRole('heading', { name: '通知投递记录', exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: '投递状态' }).selectOption('dead-letter');
  await expect(page).toHaveURL(/status=dead-letter/);
  screenshots.push(await shot(page, 'deliveries-filtered-desktop'));

  await page.getByRole('link', { name: '查看投递' }).first().click();
  const deliveryDialog = page.getByRole('dialog');
  await expect(deliveryDialog).toBeVisible();
  await expect(
    deliveryDialog.getByText('接收端返回 HTTP 400', { exact: true }),
  ).toBeVisible();
  screenshots.push(await shot(page, 'delivery-card-desktop'));
  await deliveryDialog.getByLabel('我确认重新入队这条精确的死信投递').check();
  await deliveryDialog.getByRole('button', { name: '重新入队死信投递' }).click();
  await expect(deliveryDialog.getByText(/重新入队已完成/)).toBeVisible();
  await deliveryDialog.getByRole('button', { name: '关闭', exact: true }).click();
  await expect(page).toHaveURL(/status=dead-letter/);
  await expect(page.getByRole('combobox', { name: '投递状态' })).toHaveValue('dead-letter');

  const text = await page.locator('body').innerText();
  if (text.includes(token) || text.includes(secret)) {
    throw new Error('a credential or secret value entered rendered content');
  }
  const storage = await page.evaluate(() => ({
    local: localStorage.length,
    session: sessionStorage.length,
    cookie: document.cookie,
  }));
  if (storage.local !== 0 || storage.session !== 0 || storage.cookie.includes(token)) {
    throw new Error('the token entered persistent browser state');
  }
  console.log(JSON.stringify({
    screenshots,
    deliveryId,
    tokenStored: false,
    secretRendered: false,
  }));
} finally {
  await browser.close();
}
"""


def run_browser(code: str, state: dict, artifacts: Path) -> dict:
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("node is required for the browser proof")
    result = subprocess.run(
        [node, "--input-type=module", "-e", code],
        cwd=ROOT / "web",
        env={
            **os.environ,
            "MF_PROOF_BASE": state["base"],
            "MF_PROOF_TOKEN": TOKEN,
            "MF_PROOF_SECRET": SECRET_VALUE,
            "MF_PROOF_ARTIFACTS": str(artifacts),
            "MF_PROOF_DELIVERY_ID": state["delivery_id"],
            "MF_PROOF_WEBHOOK_ID": WEBHOOK_ID,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"real Python Notification browser proof failed:\n{result.stdout}\n{result.stderr}"
        )
    return json.loads(result.stdout.strip().splitlines()[-1])


def delivery_status(repository, delivery_id: str) -> str:
    delivery = repository.get_delivery(delivery_id)
    if delivery is None:
        raise RuntimeError("proof delivery disappeared")
    return delivery.status.value


def table_counts(database: Path) -> dict[str, int]:
    if not database.exists():
        return {}
    with sqlite3.connect(database) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=Path("/tmp/mediaflow-notification-workspace-proof"),
        help="directory for screenshots and evidence.json",
    )
    args = parser.parse_args()
    artifacts = args.artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    if not (ROOT / "web" / "dist" / "index.html").exists():
        print("UNAVAILABLE: build web/dist (npm run build) before this proof")
        return 1
    root = Path(tempfile.mkdtemp(prefix="mediaflow-notification-proof-"))
    state = None
    try:
        state = start_api(root)
        wait_for_health(state["base"])
        before_counts = table_counts(root / "runtime.sqlite3")
        before_version = state["configuration"].active().version
        before_transport = len(state["transport"].requests)
        before_delivery_rows = len(state["delivery_repository"].list_deliveries(limit=100))
        before_delivery_status = delivery_status(state["delivery_repository"], state["delivery_id"])

        run_browser(READ_ONLY_BROWSER, state, artifacts)
        read_only_version = state["configuration"].active().version
        read_only_transport = len(state["transport"].requests)
        read_only_delivery_rows = len(state["delivery_repository"].list_deliveries(limit=100))
        if read_only_version != before_version:
            raise RuntimeError("read-only Notification navigation changed Active")
        if read_only_transport != before_transport:
            raise RuntimeError("read-only Notification navigation sent a test request")
        if read_only_delivery_rows != before_delivery_rows:
            raise RuntimeError("read-only Notification navigation created a delivery")
        if (
            delivery_status(state["delivery_repository"], state["delivery_id"])
            != before_delivery_status
            or before_delivery_status != "dead-letter"
        ):
            raise RuntimeError("read-only Notification navigation changed the delivery")

        browser_evidence = run_browser(BROWSER, state, artifacts)

        after_transport = len(state["transport"].requests)
        if after_transport - before_transport != 1:
            raise RuntimeError("the explicit signed test did not send exactly one recorded request")
        after_document = active_document(state["configuration"])
        after_version = state["configuration"].active().version
        if after_version <= before_version:
            raise RuntimeError("checked activation did not publish a newer Active version")
        before_webhooks = webhooks_from(state["before_document"])
        after_webhooks = webhooks_from(after_document)
        if [item["id"] for item in before_webhooks] != [item["id"] for item in after_webhooks]:
            raise RuntimeError("activation changed the Webhook identity set")
        edited = next(item for item in after_webhooks if item["id"] == WEBHOOK_ID)
        if edited["url"] != EDITED_WEBHOOK_URL:
            raise RuntimeError("the saved Webhook edit did not become Active")
        unrelated_sections = (
            "storages",
            "resourceLibraries",
            "mediaLibraries",
            "metadata",
            "naming",
            "classification",
            "organize",
        )
        for key in unrelated_sections:
            if key in state["before_document"] and (
                state["before_document"][key] != after_document.get(key)
            ):
                raise RuntimeError(f"activation changed unrelated configuration section {key}")
        status = delivery_status(state["delivery_repository"], state["delivery_id"])
        if status != "pending":
            raise RuntimeError(f"delivery recovery did not return to pending: {status}")
        deliveries = state["delivery_repository"].list_deliveries(limit=100)
        if len(deliveries) != 1:
            raise RuntimeError("the signed test or page reads created an unexpected delivery row")
        after_counts = table_counts(root / "runtime.sqlite3")
        # Reads and the explicit test never create media/configuration work;
        # the only expected row change is the selected delivery recovery.
        for table in ("tasks", "jobs"):
            if after_counts.get(table, 0) != before_counts.get(table, 0):
                raise RuntimeError(f"the Notification journey changed {table} work")
        evidence = {
            "activeVersionBefore": before_version,
            "activeVersionAfter": after_version,
            "webhookTransportRequests": after_transport - before_transport,
            "readOnlyNavigationWrote": False,
            "deliveryStatusAfter": status,
            "durableDeliveryRows": len(deliveries),
            "deliveryId": state["delivery_id"],
            "screenshots": browser_evidence["screenshots"],
        }
        (artifacts / "evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            "PASS: Notification cards, exact test, Draft publication and single-delivery recovery"
        )
        print(json.dumps(evidence, ensure_ascii=False))
        return 0
    finally:
        if state is not None:
            stop_api(state)
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
