"""Product-facing names for the three roles, shared between the sign-in
page (home.py) and the persistent header (app.py) so both call the same
role by the same name. Display-only — the underlying Role enum values
(functional_owner/manager/agent) are unchanged everywhere else.
"""
from __future__ import annotations

from rbac_scope import Role

ROLE_DISPLAY_NAME = {
    Role.FUNCTIONAL_OWNER: "ITAP Admin",
    Role.MANAGER: "Line Manager",
    Role.AGENT: "Associate",
}
