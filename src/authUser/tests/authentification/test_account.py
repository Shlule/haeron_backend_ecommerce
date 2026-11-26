"""« Mon compte » : the logged-in customer changes his information, e-mail, password and MFA."""
import pyotp
import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group

from authUser.services.tokens import generate_tokens

ME = "query { me { username email pendingEmail mfaEnabled mfaRequired } }"


@pytest.fixture
def verified_user(user):
    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
    return user


def run(client, query, user=None, variables=None):
    headers = {"Authorization": f"Bearer {generate_tokens(user)['access']}"} if user else None
    return client.query(query, variables=variables, headers=headers, assert_no_errors=False)


def login(client, password="Password123!"):
    return run(client, """mutation($p: String!) { login(identifier: "bob@test.com", password: $p) {
        access refresh mfaRequired action challenge } }""", variables={"p": password})


@pytest.mark.django_db
def test_me_needs_a_login(graphql_client, verified_user):
    assert run(graphql_client, ME).errors
    me = run(graphql_client, ME, verified_user).data["me"]
    assert me == {"username": "bob", "email": "bob@test.com", "pendingEmail": None, "mfaEnabled": False, "mfaRequired": False}


@pytest.mark.django_db
def test_update_username(graphql_client, verified_user, django_user_model):
    django_user_model.objects.create_user(username="alice", email="alice@test.com", password="x")
    query = "mutation($u: String!) { updateUsername(username: $u) { username } }"
    assert run(graphql_client, query, verified_user, {"u": "Alice"}).errors
    assert run(graphql_client, query, verified_user, {"u": "bobby"}).data["updateUsername"]["username"] == "bobby"


@pytest.mark.django_db
def test_change_password_logs_the_other_sessions_out(graphql_client, verified_user):
    other_session = login(graphql_client).data["login"]["refresh"]
    query = """mutation($c: String!) { changePassword(currentPassword: $c, newPassword: "NewPassword456!",
        passwordConfirmation: "NewPassword456!") { access refresh } }"""

    assert run(graphql_client, query, verified_user, {"c": "wrong"}).errors
    assert run(graphql_client, query, verified_user, {"c": "Password123!"}).data["changePassword"]["access"]

    assert login(graphql_client).errors
    assert login(graphql_client, "NewPassword456!").data["login"]["access"]
    refresh = run(graphql_client, "mutation($r: String!) { refreshToken(refresh: $r) { access } }", variables={"r": other_session})
    assert refresh.errors


@pytest.mark.django_db
def test_change_email_once_the_new_address_is_confirmed(graphql_client, verified_user, mailoutbox):
    query = """mutation($p: String!) { changeEmail(password: $p, email: "new@test.com", emailConfirmation: "new@test.com") {
        email pendingEmail } }"""
    assert run(graphql_client, query, verified_user, {"p": "wrong"}).errors

    result = run(graphql_client, query, verified_user, {"p": "Password123!"}).data["changeEmail"]
    assert result == {"email": "bob@test.com", "pendingEmail": "new@test.com"}
    assert mailoutbox[-1].to == ["new@test.com"]
    key = mailoutbox[-1].body.split("/compte/confirmer/")[1].split()[0]

    assert run(graphql_client, "mutation($k: String!) { verifyEmail(key: $k) }", variables={"k": key}).data["verifyEmail"]
    verified_user.refresh_from_db()
    assert verified_user.email == "new@test.com"
    assert list(EmailAddress.objects.filter(user=verified_user).values_list("email", "verified")) == [("new@test.com", True)]


@pytest.mark.django_db
def test_a_customer_with_mfa_is_asked_the_code(graphql_client, verified_user):
    secret = run(graphql_client, "mutation { startAccountMfa { secret } }", verified_user).data["startAccountMfa"]["secret"]
    enable = "mutation($c: String!) { enableAccountMfa(code: $c) { mfaEnabled } }"
    assert run(graphql_client, enable, verified_user, {"c": "000000"}).errors
    assert run(graphql_client, enable, verified_user, {"c": pyotp.TOTP(secret).now()}).data["enableAccountMfa"]["mfaEnabled"]

    result = login(graphql_client).data["login"]
    assert result["access"] is None and result["action"] == "verify"
    tokens = run(graphql_client, "mutation($ch: String!, $c: String!) { verifyMfa(challenge: $ch, code: $c) { access } }",
                 variables={"ch": result["challenge"], "c": pyotp.TOTP(secret).now()})
    assert tokens.data["verifyMfa"]["access"]

    disable = "mutation($c: String!) { disableAccountMfa(code: $c) { mfaEnabled } }"
    assert run(graphql_client, disable, verified_user, {"c": "000000"}).errors
    assert run(graphql_client, disable, verified_user, {"c": pyotp.TOTP(secret).now()}).data["disableAccountMfa"]["mfaEnabled"] is False
    assert login(graphql_client).data["login"]["access"]


@pytest.mark.django_db
def test_staff_cannot_remove_its_mfa(graphql_client, verified_user):
    verified_user.groups.add(Group.objects.create(name="admin"))
    secret = run(graphql_client, "mutation { startAccountMfa { secret } }", verified_user).data["startAccountMfa"]["secret"]
    run(graphql_client, "mutation($c: String!) { enableAccountMfa(code: $c) { mfaEnabled } }", verified_user, {"c": pyotp.TOTP(secret).now()})
    result = run(graphql_client, "mutation($c: String!) { disableAccountMfa(code: $c) { mfaEnabled } }", verified_user, {"c": pyotp.TOTP(secret).now()})
    assert result.errors
