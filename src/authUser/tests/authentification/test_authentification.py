from pprint import pprint
import pytest
from django.core import mail
from allauth.account.models import EmailAddress
from authUser.models import User


@pytest.mark.django_db
def test_login(graphql_client, user):

    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)

    mutation = """
    mutation {
    login(
        identifier:"bob@test.com"
        password:"Password123!"
    ) {
        access
        refresh
    }
}
    """

    result = graphql_client.query(mutation)

    assert result.data["login"]["access"] is not None
    assert result.data["login"]["refresh"] is not None


@pytest.mark.django_db
def test_login_email_not_verified(graphql_client, user):

    mutation = """
    mutation {
    login(
        identifier:"bob@test.com"
        password:"Password123!"
    ) {
        access
        refresh
    }
}
    """
    result = graphql_client.query(mutation, assert_no_errors=False)
    assert result.errors is not None


@pytest.mark.django_db
def test_login_wrong_password(graphql_client, user):

    mutation = """
    mutation {
        login(
            input:{
                email:"bob@test.com"
                password:"WrongPassword!"
            }
        )
    }
    """

    result = graphql_client.query(mutation, assert_no_errors=False)

    assert result.errors is not None


@pytest.mark.django_db
def test_resend_email_confirmation(graphql_client, user):

    EmailAddress.objects.create(user=user, email="bob@test.com", primary=True, verified=False)

    mutation = """
    mutation {
        resendVerificationEmail(
            email:"bob@test.com"
        )
    }
    """

    result = graphql_client.query(mutation)

    assert result.errors is None

    assert len(mail.outbox) == 1

    assert "confirm" in mail.outbox[0].subject.lower()


@pytest.mark.django_db
def test_resend_confirmation_already_verified(graphql_client, user):

    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)

    mutation = """
    mutation {
        resendVerificationEmail(
            email:"bob@test.com"
        )
    }
    """

    result = graphql_client.query(mutation, assert_no_errors=False)

    assert result.errors is not None
    assert "already verified" in result.errors[0]["message"]
