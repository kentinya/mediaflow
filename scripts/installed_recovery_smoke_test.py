#!/usr/bin/env python3
"""Prove successful recovery/confirmation with the exact installed wheel.

Only test infrastructure and an approved example config are copied. Production
imports must resolve from the wheel's site-packages, never the source checkout.
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
        (root / "scripts").mkdir()
        (root / "config").mkdir()
        shutil.copyfile(
            ROOT / "config/strategy.example.json", root / "config/strategy.example.json"
        )
        shutil.copyfile(
            ROOT / "scripts/operations_inventory_harness.py",
            root / "scripts/operations_inventory_harness.py",
        )
        shutil.copyfile(
            ROOT / "tests/test_task_center_recovery_lineage.py", root / "test_recovery.py"
        )
        probe = """
import hashlib, json, pathlib, unittest
import mediaflow
package = pathlib.Path(mediaflow.__file__).parent
assert 'site-packages' in str(package), package
print(json.dumps({'installedPackage':str(package)}, sort_keys=True), flush=True)
loaded = unittest.defaultTestLoader.discover('.', pattern='test_recovery.py')
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
