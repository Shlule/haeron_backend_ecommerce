from pprint import pprint
import pytest
import json
from haeron_guitar_api.models import Cart, CartItem, Order, OrderItem
from haeron_guitar_api.checkout.checkout_service import CheckoutService
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="test")


@pytest.fixture
def cart(db, user):
    return Cart.objects.create(user=user, is_active=True)


@pytest.fixture
def cartItem(db, user, cart, product):
    config = json.dumps({"test_config": "on est pas la pour verifier les donne"})
    config_hash = "jesuislehash"
    return CartItem.objects.create(
        cart=cart, product=product, quantity=1, unit_price=10.0, config_hash=config_hash, config_snapshot=config
    )


@pytest.mark.django_db
def test_checkout_create_order(user, cart, cartItem):

    order = CheckoutService.checkout(user=user)

    assert order.user == user
    assert order.status == "pending"

    items = order.order_items.all()

    assert len(items) == 1

    pprint(order.uuid)
    pprint(items)
