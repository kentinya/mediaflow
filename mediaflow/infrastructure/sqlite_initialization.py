"""Helpers for the one atomic initial-write transaction of a SQLite store.

``Connection.executescript`` commits any open transaction before it runs, which
would split table creation from the schema-version marker and expose a
half-initialized store to a concurrently starting service.  Initialization
therefore executes the same DDL statements one by one inside the caller's
explicit ``BEGIN IMMEDIATE`` transaction.
"""

from __future__ import annotations

import sqlite3


def execute_script(connection: sqlite3.Connection, script: str) -> None:
    """Execute every complete DDL statement without committing the caller's transaction."""

    pending = ""
    for character in script:
        pending += character
        if character != ";":
            continue
        if not sqlite3.complete_statement(pending):
            continue
        statement = pending.strip()
        pending = ""
        if statement:
            connection.execute(statement)
    if pending.strip():
        raise ValueError("schema script ended with an incomplete statement")
