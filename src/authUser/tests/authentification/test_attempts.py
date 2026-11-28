"""A password or an MFA code cannot be found by trying them all: 5 failures lock the account for 5 minutes."""
import pyotp
import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model

from authUser.services.tokens import generate_tokens

LOGIN = """mutation($i: String!, $p: String!) { login(identifier: $i, password: $p) { access challenge } }"""
VERIFY = """mutation($ch: String!, $c: String!) { verifyMfa(challenge: $ch, code: $c) { access } }"""


def login(client, password, identifier="bob"):
    return client.query(LOGIN, variables={"i": identifier, "p": password}, assert_no_errors=False)


@pytest.fixture
def verified_user(user):
    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
    return user


@pytest.mark.django_db
def test_five_wrong_passwords_lock_the_account(graphql_client, verified_user):
    get_user_model().objects.create_user(username="alice", email="alice@test.com", password="Password123!")
    EmailAddress.objects.create(email="alice@test.com", user=get_user_model().objects.get(username="alice"), verified=True)

    for i in range(5):
        assert "Invalid credentials" in login(graphql_client, f"wrong{i}").errors[0]["message"]
    # by e-mail or username, it is the same account
    assert "Too many attempts" in login(graphql_client, "Password123!", "bob@test.com").errors[0]["message"]
    # the other accounts are not affected
    assert login(graphql_client, "Password123!", "alice").data["login"]["access"]


@pytest.mark.django_db
def test_a_good_password_resets_the_count(graphql_client, verified_user):
    for i in range(4):
        login(graphql_client, f"wrong{i}")
    assert login(graphql_client, "Password123!").data["login"]["access"]
    for i in range(4):
        login(graphql_client, f"wrong{i}")
    assert login(graphql_client, "Password123!").data["login"]["access"]


@pytest.mark.django_db
def test_five_wrong_mfa_codes_lock_the_account(graphql_client, verified_user):
    headers = {"Authorization": f"Bearer {generate_tokens(verified_user)['access']}"}
    secret = graphql_client.query("mutation { startAccountMfa { secret } }", headers=headers).data["startAccountMfa"]["secret"]
    graphql_client.query("mutation($c: String!) { enableAccountMfa(code: $c) { mfaEnabled } }", variables={"c": pyotp.TOTP(secret).now()}, headers=headers)

    # a new challenge (the password is known) does not give new tries
    for _ in range(5):
        challenge = login(graphql_client, "Password123!").data["login"]["challenge"]
        assert "Invalid MFA code" in graphql_client.query(VERIFY, variables={"ch": challenge, "c": "000000"}, assert_no_errors=False).errors[0]["message"]
    challenge = login(graphql_client, "Password123!").data["login"]["challenge"]
    result = graphql_client.query(VERIFY, variables={"ch": challenge, "c": pyotp.TOTP(secret).now()}, assert_no_errors=False)
    assert "Too many attempts" in result.errors[0]["message"]
