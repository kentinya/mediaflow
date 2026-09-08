"""Bounded container entrypoint for the MediaFlow Docker image.

The entrypoint performs deployment-owned path checks before handing control to
one MediaFlow command.  It never scans Storage, contacts a Provider, creates a
Job or Task, sends a notification, or invokes a Storage mutator.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FORBIDDEN_MEDIA_ROOTS = {
    "/",
    "/data",
    "/config",
    "/etc",
    "/opt",
    "/proc",
    "/run",
    "/run/docker.sock",
    "/srv",
    "/sys",
    "/tmp",
    "/usr",
    "/var",
    "/var/run",
    "/var/run/docker.sock",
}


def load_environment_file(path: str) -> dict[str, str]:
    """Read a small deployment-owned KEY=VALUE file without logging values."""

    source = Path(path)
    try:
        content = source.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"deployment environment file could not be read: {error}") from error
    values: dict[str, str] = {}
    for line_number, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"deployment environment file line {line_number} is not KEY=VALUE")
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if not _ENV_NAME.fullmatch(name):
            raise ValueError(
                f"deployment environment file line {line_number} has an invalid variable name"
            )
        values[name] = value
    return values


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _api_token_names(document: object) -> tuple[str, ...]:
    if not isinstance(document, dict):
        return ()
    api = document.get("api")
    if not isinstance(api, dict):
        return ()
    token_env = api.get("tokenEnv")
    if isinstance(token_env, str) and _ENV_NAME.fullmatch(token_env):
        return (token_env,)
    principals = api.get("principals")
    if not isinstance(principals, list):
        return ()
    names = []
    for item in principals:
        if not isinstance(item, dict) or item.get("enabled", True) is not True:
            continue
        name = item.get("tokenEnv")
        if isinstance(name, str) and _ENV_NAME.fullmatch(name):
            names.append(name)
    return tuple(names)


def container_preflight_errors(
    config_path: str,
    data_dir: str,
    *,
    environ: dict[str, str] | None = None,
    command: tuple[str, ...] = (),
) -> list[str]:
    """Return actionable deployment errors, or an empty list when safe."""

    environment = os.environ if environ is None else environ
    errors: list[str] = []
    config = Path(config_path)
    if not config.is_file():
        errors.append(
            f"configuration file is missing or unreadable: {config_path}; "
            "mount the deployment JSON at /config/mediaflow.json"
        )
        return errors
    try:
        document = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        errors.append(f"configuration file is not valid JSON: {config_path} ({error})")
        return errors
    if not isinstance(document, dict):
        errors.append("configuration file must contain a JSON object")
        return errors

    data = Path(data_dir)
    if not data.is_dir():
        errors.append(
            f"application data directory is missing or not a directory: {data_dir}; "
            "mount the persistent local volume at /data"
        )
    elif not os.access(data, os.W_OK):
        errors.append(
            f"application data directory is not writable: {data_dir}; "
            "run the container as the documented non-root UID/GID or repair ownership"
        )

    persistence = document.get("persistence")
    if isinstance(persistence, dict):
        database = persistence.get("databasePath")
        if isinstance(database, str) and database.strip():
            path = Path(database)
            if not path.is_absolute():
                errors.append(
                    "persistence.databasePath must be an absolute path inside "
                    f"the {data_dir} persistence volume"
                )
            elif not _is_within(path, data):
                errors.append(
                    "persistence.databasePath must be inside the local "
                    f"{data_dir} persistence volume"
                )
    history = document.get("historyPath")
    if isinstance(history, str) and history.strip():
        path = Path(history)
        if not path.is_absolute():
            errors.append(
                f"historyPath must be an absolute path inside the {data_dir} persistence volume"
            )
        elif not _is_within(path, data):
            errors.append(f"historyPath must be inside the local {data_dir} persistence volume")

    storages = document.get("storages")
    if isinstance(storages, list):
        for item in storages:
            if not isinstance(item, dict) or str(item.get("type", "")).casefold() != "local":
                continue
            storage_id = str(item.get("id") or "<unnamed>")
            root = item.get("rootPath")
            if not isinstance(root, str) or not root.strip():
                errors.append(f"Local Storage {storage_id!r} rootPath must be non-empty")
                continue
            root_path = Path(root)
            normalized = root_path.resolve(strict=False)
            if (
                not root_path.is_absolute()
                or normalized.as_posix() in _FORBIDDEN_MEDIA_ROOTS
                or _is_within(normalized, data)
            ):
                errors.append(
                    f"Local Storage {storage_id!r} rootPath {root!r} is unsupported; "
                    "use an explicitly bind-mounted media path separate from /data and /config"
                )
                continue
            if not root_path.is_dir():
                errors.append(
                    f"Local Storage {storage_id!r} media mount is missing or not a directory: "
                    f"{root}; mount the directory into the container before starting"
                )
                continue
            if not os.access(root_path, os.R_OK):
                errors.append(f"Local Storage {storage_id!r} media mount is not readable: {root}")
            read_only = item.get("readOnly", False)
            if not isinstance(read_only, bool):
                errors.append(f"Local Storage {storage_id!r} readOnly must be boolean")
            elif not read_only and not os.access(root_path, os.W_OK):
                errors.append(
                    f"Local Storage {storage_id!r} media mount is not writable: {root}; "
                    "mount it read-write for the container UID/GID"
                )

    if command[:1] == ("api",):
        names = _api_token_names(document)
        missing = tuple(name for name in names if not environment.get(name))
        if missing:
            errors.append(
                "API startup requires deployment-owned environment secret"
                f"{'s' if len(missing) != 1 else ''} "
                + ", ".join(missing)
                + "; provide them in the mounted deployment environment file"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    env_file = os.environ.get("MEDIAFLOW_ENV_FILE")
    if env_file:
        try:
            os.environ.update(load_environment_file(env_file))
        except ValueError as error:
            sys.stderr.write(f"mediaflow container error: {error}\n")
            return 1
    config_path = os.environ.get("MEDIAFLOW_CONFIG", "/config/mediaflow.json")
    data_dir = os.environ.get("MEDIAFLOW_DATA_DIR", "/data")
    errors = container_preflight_errors(
        config_path,
        data_dir,
        command=tuple(args),
    )
    if errors:
        sys.stderr.write("MediaFlow container preflight failed:\n")
        for error in errors:
            sys.stderr.write(f"- {error}\n")
        return 1
    if not args:
        sys.stderr.write("mediaflow container entrypoint requires a MediaFlow command\n")
        return 1
    executable = os.environ.get("MEDIAFLOW_COMMAND", "mediaflow")
    os.execvpe(executable, [executable, *args], os.environ)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
