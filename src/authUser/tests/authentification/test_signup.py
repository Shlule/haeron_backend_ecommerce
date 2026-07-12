import pytest
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

User = get_user_model()


@pytest.mark.django_db
def test_signup(graphql_client):
    mutation = """
mutation {
    signup(
        input:{
            userName:"bob"
            email:"bob@test.com"
            password:"Password123!"
            emailConfirmation:"bob@test.com"
            passwordConfirmation:"Password123!"
            phone:"0600000000"
        }
    )
}


    """
    result = graphql_client.query(mutation)

    assert result.errors is None
    assert User.objects.filter(username="bob").exists()
    assert EmailAddress.objects.filter(email="bob@test.com", verified=False).exists()
