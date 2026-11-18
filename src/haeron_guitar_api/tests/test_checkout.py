import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from haeron_guitar_api.checkout.checkout_dto import CustomerDTO
from haeron_guitar_api.checkout.checkout_service import CheckoutService
from haeron_guitar_api.models import Cart, CartItem, Order

User = get_user_model()

CUSTOMER = CustomerDTO(
    email="jean@example.com",
    first_name="Jean",
    last_name="Dupont",
    address="1 rue de la Paix",
    postal_code="75002",
    city="Paris",
)


@pytest.fixture
def user(db):
    return User.objects.create_user(username="test")


@pytest.fixture
def cart(db, user, product):
    cart = Cart.objects.create(user=user, is_active=True)
    CartItem.objects.create(
        cart=cart, product=product, quantity=2, unit_price=10, config_hash="hash", config_snapshot={"options": {}}
    )
    return cart


def test_checkout_create_order(user, cart):
    order = CheckoutService.checkout(uuid.uuid4(), CUSTOMER, user=user)

    assert order.user == user
    assert order.status == "pending"
    assert (order.email, order.city, order.country) == ("jean@example.com", "Paris", "FR")
    assert order.total_price == 20
    assert order.order_items.get().quantity == 2
    cart.refresh_from_db()
    assert cart.is_active is False


def test_checkout_is_idempotent(user, cart):
    key = uuid.uuid4()
    first = CheckoutService.checkout(key, CUSTOMER, user=user)
    assert CheckoutService.checkout(key, CUSTOMER, user=user) == first
    assert Order.objects.count() == 1


def test_checkout_guest_cart(db, product):
    cart = Cart.objects.create(session_key="guest", is_active=True)
    CartItem.objects.create(cart=cart, product=product, quantity=1, unit_price=10, config_hash="h")
    order = CheckoutService.checkout(uuid.uuid4(), CUSTOMER, session_key="guest")
    assert order.user is None
    assert order.total_price == 10


def test_checkout_refuses_empty_cart(user):
    with pytest.raises(ValidationError):
        CheckoutService.checkout(uuid.uuid4(), CUSTOMER, user=user)


def test_checkout_refuses_missing_contact(user, cart):
    with pytest.raises(ValidationError) as error:
        CheckoutService.checkout(uuid.uuid4(), CustomerDTO("", "Jean", "", "", "", ""), user=user)
    assert "e-mail" in error.value.messages[0]
    assert not Order.objects.exists()
