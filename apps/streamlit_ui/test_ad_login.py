"""AppTest coverage for ad_auth.py's AD-login integration in home.py.

This session has no real Active Directory to bind against, so
`ad_auth.authenticate` itself is monkeypatched — but everything
downstream of that bind is exercised for real through the actual app:
home.py's Party-matching, the "not provisioned" and "invalid
credentials" error paths, and app.py's DEV_MODE force-off once a
session has authenticated via AD (the same "no Switch person escape
hatch" guarantee CML SSO passthrough gets). Same bare-script-via-AppTest
convention as the other test_*.py scripts — run directly:

    rm -f test_ad_login.db && python test_ad_login.py
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_ad_login.db"
# Any non-empty value — ad_auth.is_configured() just checks truthiness;
# the actual bind is monkeypatched below, so this never needs to
# resolve to a real server.
os.environ["AD_SERVER"] = "fake-dc.test"

import ad_auth
from party_identity.domain import Party
from services import get_services
from streamlit.testing.v1 import AppTest

services = get_services()
admin = Party(
    party_type="functional_owner",
    display_name="Priya Nair",
    attributes={"email": "priya.nair@corp.example.com"},
)
services.party_repo.add(admin)


def fake_authenticate(username, password):
    if username == "priya.nair" and password == "correct-horse":
        return ad_auth.ADUser(
            username=username, email="priya.nair@corp.example.com", display_name="Priya Nair"
        )
    if username == "someone.else" and password == "also-correct":
        # A real, valid AD account — just not one anyone has onboarded
        # into ITAP yet.
        return ad_auth.ADUser(
            username=username, email="someone.else@corp.example.com", display_name="Someone Else"
        )
    return None


ad_auth.authenticate = fake_authenticate

at = AppTest.from_file("app.py", default_timeout=20)
at.run()
assert not at.exception, f"Initial render raised: {at.exception}"

# AD login form replaces the dev-mode picker entirely once AD_SERVER is set.
assert not any(b.label == "Priya Nair" for b in at.button), (
    "Expected the picker to be replaced by a login form once AD_SERVER is configured"
)
username_inputs = [w for w in at.text_input if w.label == "Username"]
assert username_inputs, "Expected a Username field"
password_inputs = [w for w in at.text_input if w.label == "Password"]
assert password_inputs, "Expected a Password field"

print("AD login form shown instead of the picker: OK")

# Wrong password -> generic error, no crash, no leak of *why* it failed.
username_inputs[0].set_value("priya.nair").run()
password_inputs = [w for w in at.text_input if w.label == "Password"]
password_inputs[0].set_value("wrong-password").run()
sign_in_buttons = [b for b in at.button if b.label == "Sign in"]
assert sign_in_buttons, "Expected a Sign in button"
sign_in_buttons[0].click().run()
assert not at.exception, f"Failed login raised: {at.exception}"
assert any("Invalid username or password" in e.value for e in at.error), (
    "Expected the generic invalid-credentials error"
)

print("Wrong password rejected cleanly: OK")

# Right password, but no matching Party -> "not provisioned", still no picker.
username_inputs = [w for w in at.text_input if w.label == "Username"]
username_inputs[0].set_value("someone.else").run()
password_inputs = [w for w in at.text_input if w.label == "Password"]
password_inputs[0].set_value("also-correct").run()
sign_in_buttons = [b for b in at.button if b.label == "Sign in"]
sign_in_buttons[0].click().run()
assert not at.exception, f"Unmatched login raised: {at.exception}"
assert any("no ITAP account is provisioned" in e.value for e in at.error), (
    "Expected the not-provisioned error for a valid bind with no matching Party"
)
assert not any(b.label == "Priya Nair" for b in at.button), (
    "Expected still no picker fallback after an unmatched (but valid) AD login"
)

print("Valid bind with no matching Party shows 'not provisioned', not the picker: OK")

# Correct credentials, matching Party -> signed in, no Switch person escape hatch.
username_inputs = [w for w in at.text_input if w.label == "Username"]
username_inputs[0].set_value("priya.nair").run()
password_inputs = [w for w in at.text_input if w.label == "Password"]
password_inputs[0].set_value("correct-horse").run()
sign_in_buttons = [b for b in at.button if b.label == "Sign in"]
sign_in_buttons[0].click().run()
assert not at.exception, f"Successful login raised: {at.exception}"
assert "Workforce Overview" in at.title[0].value, "Expected to land on Priya's admin page"
assert not any(b.label == "Switch person" for b in at.button), (
    "Expected no 'Switch person' escape hatch after a real AD login — "
    "DEV_MODE must be force-disabled the same way CML SSO forces it off"
)

print("Correct credentials sign in; dev-mode 'Switch person' locked out: OK")
print("ALL AD LOGIN TESTS PASSED")
