#!/usr/bin/env python3
"""Prove successful recovery/confirmation with the exact installed wheel.

Only test infrastructure and an approved example config are copied. Production
imports must resolve from the wheel's site-packages, never the source checkout.
The two current Task-native journeys are the same named cases the repository
runs: one exact summary confirmation and one metadata-candidate recovery, each
of which the real Worker completes on the original Task.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RECOVERY_CASES = (
    "tests.test_manual_task_engine.ManualTaskDiscoveryTests."
    "test_native_summary_is_confirmable_on_the_same_task_from_the_center",
    "tests.test_manual_task_engine.ManualTaskDiscoveryTests."
    "test_native_metadata_candidate_confirms_on_the_same_task",
)

TEST_SUPPORT = (
    "tests/__init__.py",
    "tests/test_media_discovery.py",
    "tests/task_engine_test_helpers.py",
    "tests/test_manual_task_engine.py",
)


def smoke(wheel: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="mediaflow-wheel-recovery-") as directory:
        root = Path(directory)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / "bin" / "python"
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-deps", str(wheel.resolve())],
            cwd=root,
            check=True,
        )
        (root / "config").mkdir()
        shutil.copyfile(
            ROOT / "config/strategy.example.json", root / "config/strategy.example.json"
        )
        for relative in TEST_SUPPORT:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        probe = f"""
import json, pathlib, unittest
import mediaflow
package = pathlib.Path(mediaflow.__file__).parent
assert 'site-packages' in str(package), package
print(json.dumps({{'installedPackage':str(package)}}, sort_keys=True), flush=True)
loaded = unittest.defaultTestLoader.loadTestsFromNames({RECOVERY_CASES!r})
result = unittest.TextTestRunner(verbosity=2).run(loaded)
raise SystemExit(not result.wasSuccessful())
"""
        subprocess.run([str(python), "-c", probe], cwd=root, check=True)
    print(
        json.dumps(
            {
                "wheel": str(wheel),
                "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                "successfulInstalledRecovery": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    smoke(parser.parse_args().wheel)
