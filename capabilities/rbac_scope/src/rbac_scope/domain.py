"""Block 6: RBAC Scope — who is asking, and the exception raised when
they ask for something they may not see.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class Role(str, Enum):
    AGENT = "agent"
    MANAGER = "manager"
    FUNCTIONAL_OWNER = "functional_owner"


@dataclass(frozen=True)
class Viewer:
    party_id: UUID
    role: Role


class PermissionDenied(Exception):
    pass
