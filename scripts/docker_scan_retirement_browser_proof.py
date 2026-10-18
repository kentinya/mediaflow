#!/usr/bin/env python3
"""First-deployment Scan absence and fresh stable-size organization proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from docker_files_transfer_impact_smoke_test import build_candidate_image, image_exists, run_docker
from docker_health_smoke_test import activate_runtime, wait_for_services_healthy
from docker_smoke_test import compose_environment, free_port, wait_for_api
from docker_task_center_recovery_browser_proof import ROOT, SERVICES, _host_mount_base, api, prepare

BROWSER = r"""
import { chromium, expect } from '@playwright/test';
import fs from 'node:fs';
const base = process.env.MF_BASE, token = process.env.MF_TOKEN, output = process.env.MF_OUTPUT;
const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width:380, height:720}});
await context.tracing.start({screenshots:true,snapshots:true,sources:true});
const page = await context.newPage();
const connect = async (url) => {
  await page.goto(base + url);
  if (await page.getByLabel('API token').count()) {
    await page.getByLabel('API token').fill(token);
    await page.getByRole('button', {name:'Connect'}).click();
  }
};
try {
  await connect('/ui-v2/operations/scan/old');
  await expect(page.getByRole('heading',{name:'Route not found'})).toBeVisible();
  await page.screenshot({path:output+'/not-found-380.png',fullPage:true});
  await connect('/ui-v2/resourcelib/files?resourceLibraryId=source');
  await page.getByRole('checkbox',{name:'选择 Incoming'}).check();
  await page.getByRole('button',{name:'批量整理'}).click();
  await expect(page).toHaveURL(/discoveryId=/);
  const id = new URL(page.url()).searchParams.get('discoveryId');
  const read = async () => {
    const response=await context.request.get(base+'/api/v1/operations/organize/discoveries/'+id,
      {headers:{Authorization:'Bearer '+token}});
    expect(response.status()).toBe(200); return response.json();
  };
  await expect.poll(async()=> (await read()).status).toBe('waiting_stability');
  fs.writeFileSync(output+'/waiting.json',JSON.stringify({discoveryId:id,...await read()},null,2));
  await page.screenshot({path:output+'/waiting-380.png',fullPage:true});
  fs.writeFileSync(output+'/change-ready','ready');
  // Host changes the source during the real interval; persistent Worker owns re-observation.
  await expect.poll(()=>fs.existsSync(output+'/change-checked'), {timeout:20000}).toBe(true);
  await expect.poll(async()=> (await read()).prepared, {timeout:30000}).toBe(true);
  await expect(page.getByRole('heading',{name:'计划摘要',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'确认整理 1 项'})).toBeEnabled();
  const preview=await read();
  fs.writeFileSync(output+'/prepared.json',JSON.stringify(preview,null,2));
  await page.screenshot({path:output+'/summary-380.png',fullPage:true});
  await page.getByRole('button',{name:'确认整理 1 项'}).click();
  await expect(page).toHaveURL(/organize\/execution\//);
  const executionId = page.url().split('/execution/')[1].split('?')[0];
  await expect.poll(async()=>{
    const r=await context.request.get(base+'/api/v1/manual-executions/'+executionId,
      {headers:{Authorization:'Bearer '+token}});return (await r.json()).status;
  },{timeout:30000}).toBe('completed');
  await page.screenshot({path:output+'/result-380.png',fullPage:true});
  fs.writeFileSync(output+'/execution.json',JSON.stringify({executionId,discoveryId:id}));
} finally { await context.tracing.stop({path:output+'/trace.zip'}); await browser.close(); }
"""


READ_STATE = r"""
import json
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
with SQLiteTaskRepository('/data/mediaflow.sqlite3', read_only=True) as repo:
    tables = ('tasks', 'task_results', 'manual_executions', 'manual_execution_authorizations',
              'execution_authorizations')
    counts = {table: repo._connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
              for table in tables}
    rows = repo._connection.execute(
        'SELECT source_path,size,modified_at,fingerprint,observed_at,stable_since '
        'FROM media_discovery_observations ORDER BY source_path').fetchall()
    print(json.dumps({'counts':counts,'observations':[dict(row) for row in rows],
                     'jobs':[{'id':j.job_id,'status':j.status.value,'taskId':j.task_id,
                              'failure':j.failure_category} for j in repo.list_jobs()]}))
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--artifacts", required=True)
    args = parser.parse_args()
    output = Path(args.artifacts).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for marker in ("change-ready", "change-checked"):
        (output / marker).unlink(missing_ok=True)
    if shutil.which("docker") is None:
        print("Docker unavailable: UNAVAILABLE")
        return 1
    if not image_exists(args.image):
        build_candidate_image(args.image)
    project = f"mediaflow-scan-retirement-{os.getpid()}"
    with tempfile.TemporaryDirectory(
        prefix="mediaflow-retirement-", dir=_host_mount_base()
    ) as directory:
        root = Path(directory)
        root.chmod(0o755)
        token = secrets.token_urlsafe(24)
        port = free_port()
        config, env_file, source, target, override = prepare(root, token, port)
        document = json.loads(config.read_text())
        document["resourceLibraries"][0]["stability"] = {
            "minimumAgeSeconds": 0,
            "modifiedThresholdSeconds": 0,
            "stableSizeDurationSeconds": 5,
        }
        config.write_text(json.dumps(document))
        # No pre-existing index, Task, Result or source identity seed.
        (source / "Incoming" / "Recovery.2005.en.srt").unlink()
        for item in target.rglob("*.srt"):
            item.unlink()
        environment = compose_environment(
            root,
            args.image,
            config_file=config,
            environment_file=env_file,
            source_root=source,
            target_root=target,
            api_port=port,
        )
        environment["MEDIAFLOW_OFFLINE_PROVIDER_DIR"] = str(root / "offline_provider")
        command = [
            "docker",
            "compose",
            "-f",
            str(ROOT / "compose.yaml"),
            "-f",
            str(ROOT / "compose.media-mounts.yaml"),
            "-f",
            str(override),
            "--project-name",
            project,
        ]
        process = None
        try:
            run_docker([*command, "up", "-d", "--no-build"], environment=environment)
            wait_for_services_healthy(command, environment, expected=SERVICES)
            base = f"http://127.0.0.1:{port}"
            wait_for_api(base, token)
            activate_runtime(base, token, config)

            def container_python(code):
                return run_docker(
                    [*command, "exec", "-T", "api", "python", "-c", code],
                    environment=environment,
                ).stdout.strip()

            baseline = json.loads(container_python(READ_STATE))
            refusals = []
            for path in ("/api/v1/scans", "/api/v1/operations/scans", "/api/v1/jobs"):
                status, value = api(base, token, "POST", path, {"command": "scan"})
                expected = 400 if path == "/api/v1/jobs" else 404
                if status != expected:
                    raise RuntimeError(
                        f"unsupported input did not use its ordinary boundary: {path} {status}"
                    )
                refusals.append({"path": path, "status": status})
            rejected = json.loads(container_python(READ_STATE))
            if rejected["counts"] != baseline["counts"] or rejected["observations"]:
                raise RuntimeError("unsupported inputs created work, observation or authority")
            (output / "unsupported-inputs.json").write_text(
                json.dumps({"responses": refusals, "state": rejected}, indent=2)
            )
            process = subprocess.Popen(
                ["node", "--input-type=module", "-e", BROWSER],
                cwd=ROOT / "web",
                env={**os.environ, "MF_BASE": base, "MF_TOKEN": token, "MF_OUTPUT": str(output)},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 45
            while not (output / "change-ready").exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    stdout, stderr = process.communicate(timeout=10)
                    raise RuntimeError(f"browser failed before observation: {stdout}\n{stderr}")
                time.sleep(0.1)
            source_file = source / "Incoming" / "Recovery.2005.mkv"
            if not source_file.exists() or list(target.rglob("*.mkv")):
                raise RuntimeError("unconfirmed preparation mutated media")
            observed = json.loads(container_python(READ_STATE))
            if observed["counts"] != baseline["counts"] or len(observed["observations"]) != 1:
                raise RuntimeError("unconfirmed observation created execution authority/work")
            original_observation = observed["observations"][0]
            time.sleep(1)
            source_file.write_bytes(source_file.read_bytes() + b"changed during observation")
            changed_at = time.time()
            deadline = time.monotonic() + 15
            while True:
                reset = json.loads(container_python(READ_STATE))
                observation = reset["observations"][0]
                if observation["fingerprint"] != original_observation["fingerprint"]:
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("changed source was not re-observed")
                time.sleep(0.1)
            reset_since = observation["stable_since"] or observation["observed_at"]
            original_since = (
                original_observation["stable_since"] or original_observation["observed_at"]
            )
            if reset_since <= original_since:
                raise RuntimeError("source change did not reset the stable-size interval")
            if reset["counts"] != baseline["counts"] or not source_file.exists():
                raise RuntimeError("changing source granted work/authority before confirmation")
            (output / "observations.json").write_text(
                json.dumps({"before": observed, "reset": reset, "changedAt": changed_at}, indent=2)
            )
            (output / "change-checked").write_text("checked")
            stdout, stderr = process.communicate(timeout=90)
            (output / "browser.log").write_text(stdout + "\n" + stderr)
            if process.returncode:
                raise RuntimeError(stderr)
            from datetime import datetime

            if time.time() - datetime.fromisoformat(reset_since).timestamp() < 5:
                raise RuntimeError("confirmed before the changed source's real stable interval")
            if source_file.exists() or len(list(target.rglob("*.mkv"))) != 1:
                raise RuntimeError("exact confirmed production Worker result missing")
            completed = json.loads(container_python(READ_STATE))
            if completed["counts"]["tasks"] != 1 or completed["counts"]["manual_executions"] != 1:
                raise RuntimeError("exactly one confirmed execution was not persisted")
            run_docker([*command, "restart", "worker"], environment=environment)
            time.sleep(2)
            reopened = json.loads(container_python(READ_STATE))
            if reopened != completed:
                raise RuntimeError("resident restart changed durable completed work")
            manifest = json.loads(
                container_python(
                    "import pathlib,hashlib,json,mediaflow; "
                    "root=pathlib.Path(mediaflow.__file__).parent; "
                    "print(json.dumps({'python':{str(p.relative_to(root)):"
                    "hashlib.sha256(p.read_bytes()).hexdigest() "
                    "for p in root.rglob('*.py')},'web':{str(p.relative_to("
                    "pathlib.Path('/opt/mediaflow/web/dist'))):"
                    "hashlib.sha256(p.read_bytes()).hexdigest() "
                    "for p in pathlib.Path('/opt/mediaflow/web/dist').rglob('*') "
                    "if p.is_file()}}))"
                )
            )
            expected_python = {
                str(p.relative_to(ROOT / "mediaflow")): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (ROOT / "mediaflow").rglob("*.py")
            }
            expected_web = {
                str(p.relative_to(ROOT / "web/dist")): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (ROOT / "web/dist").rglob("*")
                if p.is_file()
            }
            if manifest != {"python": expected_python, "web": expected_web}:
                raise RuntimeError("image source or Web assets do not match this candidate")
            for path, digest in manifest["web"].items():
                served = urllib.request.urlopen(base + "/ui-v2/" + path, timeout=10).read()
                if hashlib.sha256(served).hexdigest() != digest:
                    raise RuntimeError("actual served Web asset mismatch: " + path)
            (output / "content-manifest.json").write_text(json.dumps(manifest, indent=2))
            (output / "completed-state.json").write_text(json.dumps(completed, indent=2))
            if source_file.exists() or len(list(target.rglob("*.mkv"))) != 1:
                raise RuntimeError("restart replay changed result")
            image_id = run_docker(
                ["docker", "image", "inspect", args.image, "--format", "{{.Id}}"],
                environment=environment,
            ).stdout.strip()
            (output / "evidence.json").write_text(
                json.dumps(
                    {
                        "imageId": image_id,
                        "project": project,
                        "refusals": 3,
                        "sourceExists": False,
                        "targets": 1,
                        "restartNonReplay": True,
                    },
                    indent=2,
                )
            )
            print("first-deployment absence/internal stability/confirmation/Worker/restart: PASS")
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                process.communicate(timeout=15)
            logs = run_docker(
                [*command, "logs", "--no-color"], environment=environment, check=False
            )
            (output / "containers.log").write_text(logs.stdout + logs.stderr)
            run_docker(
                [*command, "down", "-v", "--remove-orphans"], environment=environment, check=False
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
