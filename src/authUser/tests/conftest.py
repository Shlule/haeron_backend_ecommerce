import pytest
from django.core.cache import cache
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


@pytest.fixture(autouse=True)
def clear_cache():
    # failed-attempt counters and MFA challenges must not leak from one test to another
    cache.clear()
