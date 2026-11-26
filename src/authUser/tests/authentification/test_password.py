import pytest
from django.core import mail
from allauth.account.models import EmailAddress
from authUser.models import User
import re


def extract_reset_data(email):

    body = email.body

    # link of the shop page: <SHOP_URL>/compte/nouveau-mot-de-passe/<key>
    url = body.split("/compte/nouveau-mot-de-passe/")[1].split()[0]

    # the whole "<uid>-<token>" key, as the reset page gets it
    return {"key": url}


@pytest.mark.django_db
def test_reset_password(graphql_client, user):

    mutation = """
    mutation {
        resetPassword(
            email:"bob@test.com"
        )
    }
    """

    result = graphql_client.query(mutation)

    assert result.errors is None
    assert result.data["resetPassword"] is True
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_confirm_password_reset_invalid_key(graphql_client):

    mutation = """
    mutation {
        confirmPasswordReset(
            key:"invalid"
            newPassword:"Password123!"
            passwordConfirmation:"Password123!"
        )
    }
    """

    result = graphql_client.query(mutation, assert_no_errors=False)

    assert result.errors is not None


@pytest.mark.django_db
def test_reset_password_unknown_email(graphql_client):

    mutation = """
    mutation {
        resetPassword(
            email:"unknown@test.com"
        )
    }
    """

    result = graphql_client.query(mutation)

    assert result.errors is None
    assert result.data["resetPassword"] is True


@pytest.mark.django_db
def test_confirm_password_reset_success(graphql_client, user, mailoutbox):

    mutation = """
    mutation {
        resetPassword(
            email:"bob@test.com"
        )
    }
    """

    graphql_client.query(mutation)

    data = extract_reset_data(mailoutbox[0])

    mutation = f"""
    mutation {{
        confirmPasswordReset(
            key:"{data["key"]}"
            newPassword:"NewPassword123!"
            passwordConfirmation:"NewPassword123!"
        )
    }}
    """

    result = graphql_client.query(mutation)

    assert result.errors is None
    assert result.data["confirmPasswordReset"] is True

    user.refresh_from_db()

    assert user.check_password("NewPassword123!")


@pytest.mark.django_db
def test_confirm_password_reset_invalid_token(graphql_client):

    mutation = """
    mutation {
        confirmPasswordReset(
            key:"wrong-key"
            newPassword:"Password123!"
            passwordConfirmation:"Password123!"
        )
    }
    """

    result = graphql_client.query(mutation, assert_no_errors=False)

    assert result.errors is not None


@pytest.mark.django_db
def test_confirm_password_reset_weak_password(graphql_client, user, mailoutbox):

    # génération token réel

    mutation = """
    mutation {
        resetPassword(
            email:"bob@test.com"
        )
    }
    """

    graphql_client.query(mutation)

    data = extract_reset_data(mailoutbox[0])

    mutation = f"""
    mutation {{
        confirmPasswordReset(
            key:"{data["key"]}"
            newPassword:"123"
            passwordConfirmation:"123"
        )
    }}
    """

    result = graphql_client.query(mutation, assert_no_errors=False)

    assert result.errors is not None


CONFIRM = """
mutation ($key: String!) {
    confirmPasswordReset(key: $key, newPassword: "Pirate-pass-987", passwordConfirmation: "Pirate-pass-987")
}
"""


@pytest.mark.django_db
def test_only_the_key_of_the_link_changes_the_password(graphql_client, user):
    from allauth.account.forms import default_token_generator
    from allauth.account.utils import user_pk_to_url_str

    uid = user_pk_to_url_str(user)
    # the user id alone (guessable) is not enough
    forged = graphql_client.query(CONFIRM, variables={"key": f"{uid}-nimportequoi"}, assert_no_errors=False)
    assert forged.errors is not None
    user.refresh_from_db()
    assert user.check_password("Password123!")

    key = f"{uid}-{default_token_generator.make_token(user)}"
    assert graphql_client.query(CONFIRM, variables={"key": key}).data["confirmPasswordReset"] is True
    user.refresh_from_db()
    assert user.check_password("Pirate-pass-987")
    # the link works once : the new password makes it invalid
    assert graphql_client.query(CONFIRM, variables={"key": key}, assert_no_errors=False).errors is not None
