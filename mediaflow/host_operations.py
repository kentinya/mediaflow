"""Host maintenance entry for setup codes and offline SQLite recovery.

This entry is deliberately separate from the resident-service starter and from
the remaining business CLI.  It supports exactly five operations: issuing the
one-time first-administrator setup code, issuing a password reset code, and
creating, verifying or restoring a SQLite backup.  It uses the deployment
configuration, the same instance identity and the existing applicability,
lease, account and database-maintenance services.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TextIO

from mediaflow.application.accounts import AccountService
from mediaflow.container_entrypoint import (
    container_preflight_errors,
    load_environment_file,
)
from mediaflow.domain.configuration_input import reject_retired_configuration_input
from mediaflow.infrastructure.configuration_data_switch import reject_pending_configuration_switch
from mediaflow.infrastructure.runtime_lease import RuntimeDatabaseLease, RuntimeLeaseMode
from mediaflow.infrastructure.sqlite_backup import SQLiteBackupService
from mediaflow.infrastructure.sqlite_restore import SQLiteRestoreService
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.runtime_support import bootstrap_database_path, configuration_document

OPERATIONS = ("issue-setup-code", "issue-reset-code", "backup", "verify", "restore")


@contextmanager
def _shared_lease(database_path: str) -> Iterator[None]:
    """Hold the non-exclusive deployment lease for one host operation."""

    lease = RuntimeDatabaseLease(database_path, RuntimeLeaseMode.SHARED).acquire(create_parent=True)
    try:
        yield
    finally:
        lease.close()


def render_backup(value, operation: str) -> str:
    lines = [
        "",
        f"DATABASE {operation.upper()}",
        "",
        f"Path: {value.destination}",
        f"Schema: {value.schema_version} ({value.schema_kind})",
        f"Size: {value.size_bytes}",
        f"SHA-256: {value.sha256}",
        "Integrity: OK",
        f"Usable by this version: {'YES' if value.usable else 'NO'}",
        f"Checked: {value.created_at.isoformat()}",
    ]
    if value.applicability_reason:
        lines.append(f"Reason: {value.applicability_reason}")
    lines.append("")
    return "\n".join(lines)


def render_restore(value) -> str:
    return "\n".join(
        (
            "",
            "DATABASE RESTORE",
            "",
            "Status: RESTORED",
            f"Destination: {value.destination}",
            f"Schema: {value.schema_version} ({value.schema_kind})",
            f"Size: {value.size_bytes}",
            f"SHA-256: {value.sha256}",
            f"Completed: {value.completed_at.isoformat()}",
            "",
            "Next action: start only the api service first and verify the restored "
            "accounts, Active, tasks, results and audit before enabling background services.",
            "",
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mediaflow.host_operations",
        description=__doc__,
    )
    parser.add_argument("--config", help="deployment JSON configuration")
    commands = parser.add_subparsers(dest="operation", required=True)
    setup = commands.add_parser(
        "issue-setup-code", help="issue the one-time first-administrator setup code"
    )
    setup.add_argument("--json", action="store_true")
    reset = commands.add_parser("issue-reset-code", help="issue a password reset code")
    reset.add_argument("--username", required=True)
    reset.add_argument("--json", action="store_true")
    backup = commands.add_parser("backup", help="create a verified SQLite snapshot")
    backup.add_argument("--output", required=True)
    verify = commands.add_parser("verify", help="check integrity and version usability")
    verify.add_argument("path")
    restore = commands.add_parser("restore", help="restore a verified snapshot")
    restore.add_argument("backup")
    restore.add_argument("--confirm-empty-destination", action="store_true")
    return parser


def _configured_document(config_path: str | None) -> tuple[object, str]:
    path = config_path or os.environ.get("MEDIAFLOW_CONFIG", "/config/mediaflow.json")
    document = configuration_document(path)
    reject_retired_configuration_input(document)
    return document, path


def _require_supported_configuration(
    config_path: str, data_dir: str, *, check_database: bool
) -> None:
    errors = container_preflight_errors(
        config_path,
        data_dir,
        service=None,
        check_media=False,
        check_database=check_database,
    )
    if errors:
        raise ValueError("; ".join(errors))


def _issue_account_code(
    arguments: argparse.Namespace,
    database_path: str,
    *,
    stdout: TextIO,
) -> int:
    with _shared_lease(database_path), SQLiteTaskRepository(database_path) as repository:
        service = AccountService(repository)
        if arguments.operation == "issue-setup-code":
            code, expires_at = service.issue_first_admin_code()
            document = {
                "purpose": "first_administrator",
                "expiresAt": expires_at.isoformat(),
                "code": code,
            }
        else:
            code, expires_at = service.issue_reset_code(arguments.username)
            document = {
                "purpose": "reset_password",
                "username": arguments.username,
                "expiresAt": expires_at.isoformat(),
                "code": code,
            }
    if arguments.json:
        stdout.write(json.dumps(document, sort_keys=True) + "\n")
    else:
        stdout.write(
            "\nONE-TIME CODE\n\n"
            f"Purpose: {document['purpose']}\n"
            f"Expires: {document['expiresAt']}\n"
            f"Code: {document['code']}\n\n"
            "Enter this code only in the MediaFlow sign-in page. It is shown once "
            "and cannot be recovered.\n\n"
        )
    return 0


def _database_operation(
    arguments: argparse.Namespace,
    database_path: str,
    *,
    stdout: TextIO,
) -> int:
    if arguments.operation == "restore":
        if not arguments.confirm_empty_destination:
            raise ValueError("restore requires --confirm-empty-destination")
        with RuntimeDatabaseLease(database_path, RuntimeLeaseMode.EXCLUSIVE):
            reject_pending_configuration_switch(database_path)
            result = SQLiteRestoreService(arguments.backup, database_path).restore(
                confirmed_empty_destination=True
            )
        stdout.write(render_restore(result))
        return 0
    with _shared_lease(database_path):
        if arguments.operation == "backup":
            reject_pending_configuration_switch(database_path)
            result = SQLiteBackupService(database_path).backup(arguments.output)
        else:
            result = SQLiteBackupService(database_path).verify(arguments.path)
    stdout.write(render_backup(result, arguments.operation))
    return 0


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    parser = _parser()
    arguments = parser.parse_args(argv)
    env_file = os.environ.get("MEDIAFLOW_ENV_FILE")
    if env_file:
        try:
            os.environ.update(load_environment_file(env_file))
        except ValueError as error:
            error_output.write(f"mediaflow host error: {error}\n")
            return 1
    try:
        document, config_path = _configured_document(arguments.config)
        database_path = bootstrap_database_path(document)
        _require_supported_configuration(
            config_path,
            os.environ.get("MEDIAFLOW_DATA_DIR", "/data"),
            check_database=arguments.operation != "verify",
        )
        if arguments.operation in {"issue-setup-code", "issue-reset-code"}:
            reject_pending_configuration_switch(database_path)
            return _issue_account_code(arguments, database_path, stdout=output)
        return _database_operation(arguments, database_path, stdout=output)
    except (OSError, ValueError, LookupError, RuntimeError) as error:
        error_output.write(f"mediaflow host error: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
