from pprint import pprint
import pytest
from django.core import mail
from allauth.account.models import EmailAddress
from authUser.models import User
import re


def extract_reset_data(email):

    body = email.body

    url = body.split("/password/reset/key/")[1]
    url = url.split("/")[0]

    uid, key = url.split("-", 1)

    return {
        "uid": uid,
        "key": key,
    }


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
            uid:"invalid"
            key:"invalid"
            newPassword:"Password123!"
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
            uid:"{data["uid"]}"
            key:"{data["key"]}"
            newPassword:"NewPassword123!"
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
            uid:"{data["uid"]}"
            key:"{data["key"]}"
            newPassword:"123"
        )
    }}
    """

    result = graphql_client.query(mutation, assert_no_errors=False)

    assert result.errors is not None
