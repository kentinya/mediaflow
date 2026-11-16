"""Authority types for definition-pinned scheduled and Run once execution.

The independent unattended grant product is retired.  Current authority is the
published Enabled definition (scheduled) or one explicit Run once command
(single run), checked against the *actual current* configured principal
permission at admission and again at every unperformed effect boundary.
"""

from __future__ import annotations

from typing import Protocol

from mediaflow.domain.security import ApiPermission


class CurrentPermissionAuthority(Protocol):
    """Read-only authority for the current configured principal permissions."""

    def has_permission(self, principal_id: str, permission: str | ApiPermission) -> bool: ...


__all__ = ["CurrentPermissionAuthority"]
