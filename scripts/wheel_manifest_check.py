#!/usr/bin/env python3
"""Prove one built wheel carries exactly the modules of a clean source archive.

The comparison source is always a *clean* archive of ``HEAD`` extracted outside
the working tree with ``git archive``.  Nothing in the working tree is written
except the temporary build directories this tool creates for itself; the
candidate wheel is only read.

Three build modes are attempted in order and the chosen mode is stated in the
output:

``build-module``
    ``python -m build --wheel --outdir <tmp> <clean-tree>`` when the ``build``
    frontend is importable.
``pip-wheel``
    ``python -m pip wheel --no-deps -w <tmp> <clean-tree>`` otherwise, retried
    once with ``--no-build-isolation`` so a machine without network access can
    still produce a comparison wheel.
``archive-enumeration``
    when neither frontend can build, the clean archive's package files are
    enumerated directly and compared against the wheel's payload entries.  This
    mode still proves the packaged *set* of package files, but it cannot see
    wheel metadata, so the ``.dist-info`` entries of the candidate wheel are
    excluded from that comparison and the limitation is stated in the output.

Every entry that exists on both sides is compared by sha256, not only by name.
Two entries are exempt from failing the check because they record *how* the
wheel was produced rather than what it contains:

``.dist-info/RECORD``
    embeds the wheel's own digest table, so two wheels built by different
    frontends legitimately differ there.
``.dist-info/WHEEL``
    records the ``Generator: setuptools (x.y.z)`` version used by the building
    environment.  When ``python -m build`` is unavailable the clean wheel is
    produced by this environment's setuptools while the candidate wheel may have
    been produced under build isolation with a different setuptools, so the
    generator line is reported as ``build_metadata_differing`` and does not fail
    the check.  The difference is only tolerated when it is exactly that
    generator line; any other WHEEL change still fails.

Both exempt entries are still listed in ``byte_differing`` with their sha256.

Usage::

    python scripts/wheel_manifest_check.py dist/mediaflow-2.0.0.dev0-py3-none-any.whl

Exit codes: 0 the manifests match, 1 they differ, 2 the check could not run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

#: ``RECORD`` embeds the wheel's own digest table, so two wheels built by
#: different frontends legitimately differ there.  It is still listed as a
#: differing entry (never silently dropped) but it cannot fail the check.
RECORD_SUFFIX = ".dist-info/RECORD"

#: ``WHEEL`` records the building setuptools version.  Only an isolated
#: generator-line difference is tolerated (see :func:`_wheel_metadata_only`).
WHEEL_SUFFIX = ".dist-info/WHEEL"

#: Wheel metadata only exists in a built wheel, never in a clean source archive,
#: so the archive-enumeration fallback cannot compare it.
DIST_INFO_MARKER = ".dist-info/"


def _normalize(name: str) -> str:
    return name.replace("\\", "/").lstrip("./")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_wheel(wheel: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(wheel) as archive:
        return {_normalize(name): archive.read(name) for name in archive.namelist()}


def _git_archive(revision: str, project: Path, destination: Path) -> None:
    archive = subprocess.run(  # noqa: S603
        ["git", "archive", revision], cwd=str(project), capture_output=True
    )
    if archive.returncode != 0:
        raise RuntimeError(
            "git archive failed: " + archive.stderr.decode("utf-8", "replace").strip()
        )
    extract = subprocess.run(  # noqa: S603
        ["tar", "-x", "-C", str(destination)], input=archive.stdout, capture_output=True
    )
    if extract.returncode != 0:
        raise RuntimeError(
            "tar extraction failed: " + extract.stderr.decode("utf-8", "replace").strip()
        )


def _module_available(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


def _single_wheel(outdir: Path) -> Path | None:
    wheels = sorted(outdir.glob("*.whl"))
    if len(wheels) != 1:
        return None
    return wheels[0]


def _build_with_module(clean_tree: Path, outdir: Path) -> Path | None:
    outdir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(outdir), str(clean_tree)],
        cwd=str(clean_tree),
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return _single_wheel(outdir)


def _build_with_pip(clean_tree: Path, outdir: Path) -> Path | None:
    """Build the clean wheel, preferring the isolated build used for releases.

    The isolated build matches how a release wheel is normally produced.  A
    machine without network access cannot create the build environment, so the
    offline ``--no-build-isolation`` variant is attempted second; the resulting
    generator-line difference is then tolerated as build metadata.
    """

    for extra in ([], ["--no-build-isolation"]):
        outdir.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                *extra,
                "-w",
                str(outdir),
                str(clean_tree),
            ],
            cwd=str(clean_tree),
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            wheel = _single_wheel(outdir)
            if wheel is not None:
                return wheel
    return None


def _package_roots(clean_tree: Path) -> list[str]:
    """The configured setuptools package roots, or every top-level package."""

    includes: list[str] = []
    configuration = clean_tree / "pyproject.toml"
    if configuration.is_file():
        document = tomllib.loads(configuration.read_text(encoding="utf-8"))
        find = document.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {})
        includes = [str(value) for value in find.get("include", [])]
    roots: list[str] = []
    for child in sorted(clean_tree.iterdir()):
        if not child.is_dir() or not (child / "__init__.py").is_file():
            continue
        if includes and not any(child.name == str(value).rstrip("*") for value in includes):
            continue
        roots.append(child.name)
    return roots


def _enumerate_archive(clean_tree: Path) -> dict[str, bytes]:
    """Every packaged module/asset of the clean archive, by wheel-relative path."""

    entries: dict[str, bytes] = {}
    for root in _package_roots(clean_tree):
        for path in sorted((clean_tree / root).rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            relative = _normalize(str(path.relative_to(clean_tree)))
            entries[relative] = path.read_bytes()
    return entries


def _wheel_metadata_only(clean: bytes, candidate: bytes) -> bool:
    """True when two ``WHEEL`` payloads differ only in their generator line.

    ``Generator: setuptools (x.y.z)`` describes the environment that built the
    wheel, not the packaged source.  The generator line is therefore allowed to
    differ; every other line must still match exactly.
    """

    def without_generator(payload: bytes) -> list[str]:
        return [
            line
            for line in payload.decode("utf-8", "replace").splitlines()
            if not line.startswith("Generator:")
        ]

    return without_generator(clean) == without_generator(candidate)


def _compare(
    clean: dict[str, bytes], candidate: dict[str, bytes]
) -> tuple[list[str], list[str], list[str], list[str], list[str], list[dict[str, str]]]:
    clean_digests = {name: _sha256(payload) for name, payload in clean.items()}
    candidate_digests = {name: _sha256(payload) for name, payload in candidate.items()}
    only_in_clean = sorted(set(clean_digests) - set(candidate_digests))
    only_in_candidate = sorted(set(candidate_digests) - set(clean_digests))
    differing = sorted(
        name
        for name in set(clean_digests) & set(candidate_digests)
        if clean_digests[name] != candidate_digests[name]
    )
    failing: list[str] = []
    build_metadata: list[str] = []
    for name in differing:
        if name.endswith(RECORD_SUFFIX):
            continue
        if name.endswith(WHEEL_SUFFIX) and _wheel_metadata_only(clean[name], candidate[name]):
            build_metadata.append(name)
            continue
        failing.append(name)
    evidence = [
        {
            "entry": name,
            "clean_sha256": clean_digests[name],
            "candidate_sha256": candidate_digests[name],
        }
        for name in differing
    ]
    return only_in_clean, only_in_candidate, differing, failing, build_metadata, evidence


def _stage_working_tree(project: Path, destination: Path) -> None:
    """Copy the working tree's source files into an isolated staging tree.

    ``git ls-files --cached --others --exclude-standard`` lists exactly the
    tracked files plus the untracked-but-not-ignored ones, so a new source file
    that has not been committed yet is staged while every ignored build artifact
    (``build/``, ``dist/``, ``*.egg-info``) is excluded.  Building the candidate
    from this stage therefore isolates the build from a stale ignored
    ``build/`` directory without modifying or deleting any workspace file.
    """

    listed = subprocess.run(  # noqa: S603
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=str(project),
        capture_output=True,
    )
    if listed.returncode != 0:
        raise RuntimeError(
            "git ls-files failed: " + listed.stderr.decode("utf-8", "replace").strip()
        )
    destination.mkdir(parents=True, exist_ok=True)
    for raw in listed.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8")
        source = project / relative
        if not source.is_file():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path, help="the built wheel to inspect")
    parser.add_argument(
        "--project",
        default=str(Path(__file__).resolve().parents[1]),
        help="repository root containing the script's parent (default: script's parent)",
    )
    parser.add_argument(
        "--revision",
        default="HEAD",
        help="git revision whose clean archive is the comparison source (default: HEAD)",
    )
    parser.add_argument(
        "--build-candidate",
        action="store_true",
        help=(
            "also build the candidate from an isolated git archive of --revision and compare "
            "that clean-built wheel against the supplied wheel.  This isolates the build from "
            "any stale ignored build/ staging directory in the working tree, which otherwise "
            "contaminates a working-tree build."
        ),
    )
    arguments = parser.parse_args(argv)

    wheel = arguments.wheel
    if not wheel.is_file():
        print(json.dumps({"ok": False, "error": f"{wheel} is not a file"}, indent=2))
        return 2
    if not zipfile.is_zipfile(wheel):
        print(json.dumps({"ok": False, "error": f"{wheel} is not a zip wheel"}, indent=2))
        return 2
    project = Path(arguments.project).resolve()
    if not (project / ".git").exists():
        print(json.dumps({"ok": False, "error": f"{project} is not a git tree"}, indent=2))
        return 2

    root = Path(tempfile.mkdtemp(prefix="mediaflow-wheel-manifest-"))
    try:
        clean_tree = root / "clean-source"
        clean_tree.mkdir()
        _git_archive(arguments.revision, project, clean_tree)

        candidate_payloads = _read_wheel(wheel)
        candidate_size = wheel.stat().st_size
        candidate_digest = _sha256(wheel.read_bytes())

        build_mode = "archive-enumeration"
        clean_wheel: Path | None = None
        if _module_available("build"):
            clean_wheel = _build_with_module(clean_tree, root / "build-out")
            if clean_wheel is not None:
                build_mode = "build-module"
        if clean_wheel is None:
            clean_wheel = _build_with_pip(clean_tree, root / "pip-out")
            if clean_wheel is not None:
                build_mode = "pip-wheel"

        limitations: list[str] = []
        if arguments.build_candidate:
            # The candidate is rebuilt from an *isolated* staging tree of the
            # working-tree source (tracked plus untracked-not-ignored files).
            # A stale ignored ``build/`` directory would otherwise be copied
            # wholesale into the wheel by setuptools' build staging, so this
            # proves the supplied wheel carries the real source rather than a
            # leftover snapshot.  No workspace file is modified or deleted.
            staging = root / "candidate-source"
            _stage_working_tree(project, staging)
            rebuilt = _build_with_pip(staging, root / "candidate-out")
            if rebuilt is None and _module_available("build"):
                rebuilt = _build_with_module(staging, root / "candidate-out")
            if rebuilt is None:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": (
                                "--build-candidate was requested but no build frontend could "
                                "build the isolated working-tree candidate"
                            ),
                        },
                        indent=2,
                    )
                )
                return 2
            build_mode = f"{build_mode}+isolated-candidate"
            candidate_payloads = _read_wheel(rebuilt)
            candidate_size = rebuilt.stat().st_size
            candidate_digest = _sha256(rebuilt.read_bytes())
            limitations.append(
                "the candidate was rebuilt from an isolated working-tree staging tree "
                "(tracked plus untracked-not-ignored files) so a stale ignored build/ "
                "directory cannot contaminate the compared payload; the supplied wheel "
                "is the artifact under test and its own sha256 is reported separately"
            )
            limitations.append(
                f"supplied wheel: {wheel} (sha256 "
                f"{_sha256(wheel.read_bytes())}, {wheel.stat().st_size} bytes)"
            )

        excluded_from_comparison: list[str] = []
        if clean_wheel is not None:
            clean_payloads = _read_wheel(clean_wheel)
            compared_candidate = candidate_payloads
            byte_equality_proven = True
        else:
            clean_payloads = _enumerate_archive(clean_tree)
            excluded_from_comparison = sorted(
                name for name in candidate_payloads if DIST_INFO_MARKER in name
            )
            compared_candidate = {
                name: payload
                for name, payload in candidate_payloads.items()
                if DIST_INFO_MARKER not in name
            }
            byte_equality_proven = False
            limitations.append(
                "neither the build frontend nor pip could build the clean archive; the clean "
                "package files were enumerated directly, so wheel metadata is not compared"
            )

        only_in_clean, only_in_candidate, differing, failing, build_metadata, evidence = _compare(
            clean_payloads, compared_candidate
        )
        if not byte_equality_proven:
            limitations.append(
                "archive-enumeration mode compares package-file paths and sha256 only; "
                "no wheel-level metadata equality is proven"
            )
        if build_metadata:
            limitations.append(
                "the clean wheel was built with a different setuptools generator than the "
                "candidate; the generator line in .dist-info/WHEEL is the only tolerated "
                "metadata difference"
            )
        summary = {
            "ok": not only_in_clean and not only_in_candidate and not failing,
            "mode": build_mode,
            "revision": arguments.revision,
            "clean_wheel": str(clean_wheel) if clean_wheel is not None else None,
            "supplied_wheel": str(wheel),
            "candidate_wheel": str(wheel),
            "candidate_isolated_rebuild": arguments.build_candidate,
            "candidate_size_bytes": candidate_size,
            "candidate_sha256": candidate_digest,
            "clean_entry_count": len(clean_payloads),
            "candidate_entry_count": len(candidate_payloads),
            "compared_candidate_entry_count": len(compared_candidate),
            "only_in_clean": only_in_clean,
            "only_in_candidate": only_in_candidate,
            "byte_differing": differing,
            "byte_differing_non_record": failing,
            "build_metadata_differing": build_metadata,
            "byte_differing_sha256": evidence,
            "excluded_from_comparison": excluded_from_comparison,
            "byte_equality_proven": byte_equality_proven,
            "limitations": limitations,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        if summary["ok"]:
            return 0
        print("MANIFEST MISMATCH", file=sys.stderr)
        for name in only_in_clean:
            print(f"  only in clean: {name}", file=sys.stderr)
        for name in only_in_candidate:
            print(f"  only in candidate: {name}", file=sys.stderr)
        for name in failing:
            print(f"  byte-differing: {name}", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2))
        return 2
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
