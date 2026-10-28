from logging import config
from pprint import pprint
from django.test import TestCase
from django.contrib.auth import get_user_model

from ..models import Cart, CartItem, Product, ProductType
from ..cart.cart_service import CartService
from ..cart.cart_dto import CreateCartDTO

User = get_user_model()


class CartServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user1")
        self.product_type = ProductType.objects.create(code="custom_piece")
        self.product = Product.objects.create(name="Custom Guitar", price=100, product_type=self.product_type)

    def test_create_guest_cart(self):
        dto = CreateCartDTO(session_key="abc")

        cart = CartService.get_or_create_cart(dto)

        self.assertEqual(cart.session_key, "abc")
        self.assertIsNone(cart.user)
        self.assertTrue(cart.is_active)

    def test_create_user_cart(self):
        dto = CreateCartDTO(user=self.user)
        cart = CartService.get_or_create_cart(dto)

        self.assertEqual(cart.user, self.user)
        self.assertIsNone(cart.session_key)
        self.assertTrue(cart.is_active)

    def test_get_existing_cart(self):
        dto = CreateCartDTO(user=self.user)

        cart1 = CartService.get_or_create_cart(dto)
        cart2 = CartService.get_or_create_cart(dto)

        self.assertEqual(cart1.uuid, cart2.uuid)
        self.assertEqual(Cart.objects.count(), 1)

    def test_merge_guest_without_existing_user(self):
        guest_cart = Cart.objects.create(session_key="guest")

        merged_cart = CartService.merge_guest_to_user(guest_cart, self.user)

        self.assertEqual(merged_cart.user, self.user)
        self.assertIsNone(merged_cart.session_key)

    def test_merge_guest_with_existing_user_cart(self):
        user_cart = Cart.objects.create(user=self.user, is_active=True)
        guest_cart = Cart.objects.create(session_key="guest", is_active=True)

        CartItem.objects.create(
            cart=guest_cart,
            product=self.product,
            quantity=1,
            unit_price=100,
            config_snapshot={"wood": "mapple"},
            config_hash="ahah",
        )
        CartItem.objects.create(
            cart=user_cart,
            product=self.product,
            quantity=2,
            unit_price=100,
            config_snapshot={"wood": "mapple"},
            config_hash="ahah",
        )

        merged_cart = CartService.merge_guest_to_user(guest_cart, self.user)
        item = merged_cart.cart_items.first()

        self.assertEqual(item.quantity, 3)
        self.assertEqual(merged_cart.uuid, user_cart.uuid)

    def test_merge_with_different_config_snapshot(self):
        user_cart = Cart.objects.create(user=self.user, is_active=True)
        guest_cart = Cart.objects.create(session_key="guest", is_active=True)

        CartItem.objects.create(
            cart=user_cart,
            product=self.product,
            quantity=1,
            unit_price=100,
            config_snapshot={"wood": "mapple"},
            config_hash="ahah",
        )
        CartItem.objects.create(
            cart=user_cart,
            product=self.product,
            quantity=2,
            unit_price=100,
            config_snapshot={"wood": "mahogany"},
            config_hash="bhbh",
        )

        merged_cart = CartService.merge_guest_to_user(guest_cart, self.user)
        self.assertEqual(merged_cart.cart_items.count(), 2)
        items_map = {tuple(item.config_snapshot.items()): item for item in merged_cart.cart_items.all()}

        self.assertEqual(items_map[(("wood", "mapple"),)].quantity, 1)
        self.assertEqual(items_map[(("wood", "mahogany"),)].quantity, 2)

    def test_guest_cart_deactivated_after_merge(self):
        guest_cart = Cart.objects.create(session_key="guest", is_active=True)
        user_cart = Cart.objects.create(user=self.user, is_active=True)

        CartService.merge_guest_to_user(guest_cart, self.user)
        guest_cart.refresh_from_db()
        self.assertFalse(guest_cart.is_active)

    def test_item_moved_to_user_cart(self):
        user_cart = Cart.objects.create(user=self.user, is_active=True)
        guest_cart = Cart.objects.create(session_key="guest", is_active=True)

        item = CartItem.objects.create(
            cart=guest_cart,
            product=self.product,
            quantity=1,
            unit_price=100,
            config_snapshot={"wood": "mapple"},
            config_hash="ahah",
        )

        CartService.merge_guest_to_user(guest_cart, self.user)
        item.refresh_from_db()
        self.assertEqual(item.cart, user_cart)

    def test_soft_delete_cart(self):
        cart = Cart.objects.create(session_key="abc", is_active=True)

        cart.is_active = False
        cart.save()

        cart.refresh_from_db()
        self.assertFalse(cart.is_active)

    def test_merge_empty_guest_cart(self):
        user_cart = Cart.objects.create(user=self.user, is_active=True)
        guest_cart = Cart.objects.create(session_key="guest", is_active=True)

        merged_cart = CartService.merge_guest_to_user(guest_cart, self.user)

        self.assertEqual(merged_cart.cart_items.count(), 0)
