#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path


def run(command: list[str], *, cwd: Path, environment: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=environment, check=True)  # noqa: S603


def inspect_wheel(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    required = {
        "mediaflow/cli.py",
        "mediaflow/final_cli.py",
        "mediaflow/infrastructure/sqlite_backup.py",
        "mediaflow/infrastructure/sqlite_restore.py",
        "mediaflow/infrastructure/runtime_lease.py",
        "mediaflow/infrastructure/upgrade_preflight.py",
    }
    missing = sorted(required - names)
    if missing:
        raise ValueError(f"wheel is missing required modules: {', '.join(missing)}")
    forbidden = tuple(
        name
        for name in names
        if name.startswith(("tests/", "config/"))
        or "/__pycache__/" in name
        or name.endswith((".pyc", ".sqlite", ".sqlite3", ".db", ".env"))
        or "alist.json" in name
    )
    if forbidden:
        raise ValueError(f"wheel contains forbidden runtime/user files: {', '.join(forbidden)}")


def configured_copy(source: Path, target: Path, database: Path) -> None:
    document = json.loads(source.read_text(encoding="utf-8"))
    document["persistence"] = {"databasePath": str(database)}
    target.write_text(json.dumps(document), encoding="utf-8")


def smoke(wheel: Path, project: Path) -> None:
    inspect_wheel(wheel)
    with tempfile.TemporaryDirectory(prefix="mediaflow-wheel-smoke-") as directory:
        root = Path(directory)
        environment = os.environ.copy()
        for name in tuple(environment):
            if "TOKEN" in name or "PASSWORD" in name or "SECRET" in name or "API_KEY" in name:
                environment.pop(name)
        virtual_environment = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(virtual_environment)
        scripts = virtual_environment / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        mediaflow = scripts / ("mediaflow.exe" if os.name == "nt" else "mediaflow")
        run(
            [str(python), "-m", "pip", "install", "--no-deps", str(wheel.resolve())],
            cwd=root,
            environment=environment,
        )
        run([str(mediaflow), "--help"], cwd=root, environment=environment)
        database = root / "runtime.sqlite3"
        run(
            [
                str(python),
                "-c",
                "from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository; "
                f"SQLiteTaskRepository({str(database)!r}).close()",
            ],
            cwd=root,
            environment=environment,
        )
        configurations = []
        for name in ("strategy.example.json", "mediaflow.phase13.2.example.json"):
            target = root / name
            configured_copy(project / "config" / name, target, database)
            configurations.append(target)
            run(
                [str(mediaflow), "--config", str(target), "config", "validate"],
                cwd=root,
                environment=environment,
            )
        backup = root / "backup.sqlite3"
        run(
            [
                str(mediaflow),
                "--config",
                str(configurations[0]),
                "database",
                "backup",
                "--output",
                str(backup),
            ],
            cwd=root,
            environment=environment,
        )
        restored = root / "restored-runtime.sqlite3"
        restore_configuration = root / "restore.json"
        configured_copy(
            project / "config" / "strategy.example.json", restore_configuration, restored
        )
        lease_script = (
            "import sys; from mediaflow.infrastructure.runtime_lease import "
            "RuntimeDatabaseLease,RuntimeLeaseMode; "
            "lease=RuntimeDatabaseLease(sys.argv[1],RuntimeLeaseMode.SHARED).acquire(); "
            "print('READY',flush=True); input()"
        )
        with subprocess.Popen(
            [str(python), "-c", lease_script, str(restored)],
            cwd=root,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as holder:
            assert holder.stdout is not None
            if holder.stdout.readline().strip() != "READY":
                raise RuntimeError("installed-wheel runtime lease holder did not start")
            blocked = subprocess.run(
                [
                    str(mediaflow),
                    "--config",
                    str(restore_configuration),
                    "database",
                    "restore",
                    str(backup),
                    "--confirm-empty-destination",
                ],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            if blocked.returncode != 2 or restored.exists():
                raise RuntimeError(
                    "installed-wheel restore did not fail closed on lease contention"
                )
            holder.kill()
            holder.communicate(timeout=5)
        run(
            [
                str(mediaflow),
                "--config",
                str(restore_configuration),
                "database",
                "restore",
                str(backup),
                "--confirm-empty-destination",
            ],
            cwd=root,
            environment=environment,
        )
        run(
            [
                str(mediaflow),
                "--config",
                str(restore_configuration),
                "database",
                "verify",
                str(restored),
            ],
            cwd=root,
            environment=environment,
        )
        run(
            [
                str(mediaflow),
                "--config",
                str(configurations[0]),
                "upgrade",
                "check",
                "--backup",
                str(backup),
            ],
            cwd=root,
            environment=environment,
        )
        run(
            [
                str(mediaflow),
                "--config",
                str(configurations[0]),
                "database",
                "verify",
                str(backup),
            ],
            cwd=root,
            environment=environment,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an isolated MediaFlow wheel")
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    arguments = parser.parse_args()
    smoke(arguments.wheel, arguments.project.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
