import pytest
from authUser.tests.factories import UserFactory
from django.test import Client
from strawberry.django.test import GraphQLTestClient
from authUser.models import User


@pytest.fixture
def graphql_client():
    client = Client()
    return GraphQLTestClient(client)


@pytest.fixture
def user():
    return User.objects.create_user(username="bob", email="bob@test.com", password="Password123!")
