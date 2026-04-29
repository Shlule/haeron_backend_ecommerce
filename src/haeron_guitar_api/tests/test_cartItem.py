from itertools import product
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from uuid import uuid4

from ..models import CartItem, Cart, Product
from ..cartItem.cartItem_service import CartItemService, CartItemFactory, ConfigHashService
from ..cartItem.cartItem_utils import CartItemConfigResolver
from ..cartItem.cartItem_dto import createCartItemDTO

User = get_user_model()


class CartItemServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test")
        self.cart = Cart.objects.create(user=self.user, is_active=True)
        self.product = Product.objects.create(name="Guitar Custom", price=100)

    # SECTION - adding quantity
    def test_add_item_success(self):
        dto = createCartItemDTO(cart_id=self.cart.uuid, product_id=self.product.uuid, quantity=2)
        item = CartItemService.add_item(dto)

        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.cart, self.cart)
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.unit_price, 100)

    def test_add_item_invalide_quantity(self):

        dto = createCartItemDTO(cart_id=self.cart.uuid, product_id=self.product.uuid, quantity=0)

        with self.assertRaises(ValidationError):
            CartItemService.add_item(dto)

    def test_add_item_merge_same(self):
        dto = createCartItemDTO(cart_id=self.cart.uuid, product_id=self.product.uuid, quantity=1)

        CartItemService.add_item(dto)
        item = CartItemService.add_item(dto)

        self.assertEqual(item.quantity, 2)
        self.assertEqual(CartItem.objects.count(), 1)

    def test_add_item_config_agregation(self):
        dto1 = createCartItemDTO(cart_id=self.cart.uuid, product_id=self.product.uuid, quantity=1)
        dto2 = createCartItemDTO(
            cart_id=self.cart.uuid, product_id=self.product.uuid, quantity=1, part_model_id=uuid4()
        )

        CartItemService.add_item(dto1)
        CartItemService.add_item(dto2)

        self.assertEqual(CartItem.objects.count(), 2)

    #!SECTION

    # SECTION - update quantity
    def test_update_quantity_success(self):
        item = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=1, unit_price=100, config_hash="abs", config_snapshot={}
        )
        updated = CartItemService.update_quantity(item.uuid, 5)

        self.assertEqual(updated.quantity, 5)

    def test_update_quantity_to_zero_delete(self):
        item = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=1, unit_price=100, config_hash="abs", config_snapshot={}
        )
        result = CartItemService.update_quantity(item.uuid, 0)

        self.assertIsNone(result)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_update_quantity_invalid(self):
        item = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=1, unit_price=100, config_hash="abs", config_snapshot={}
        )
        with self.assertRaises(ValidationError):
            CartItemService.update_quantity(item.quantity, -2)

    def test_update_quantity_not_found(self):
        with self.assertRaises(ValidationError):
            CartItemService.update_quantity(uuid4(), 1)

    #!SECTION

    # SECTION - delete
    def test_delete_item_success(self):
        item = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=1, unit_price=100, config_hash="abs", config_snapshot={}
        )
        result = CartItemService.delete_item(item.uuid)

        self.assertTrue(result)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_delete_item_not_found(self):
        result = CartItemService.delete_item(uuid4())
        self.assertFalse(result)

    def test_delete_item_bulk_sucess(self):
        item1 = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=1, unit_price=100, config_hash="a", config_snapshot={}
        )
        item2 = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=1, unit_price=100, config_hash="b", config_snapshot={}
        )

        deleted = CartItemService.delete_items([item1.uuid, item2.uuid])

        self.assertEqual(deleted, 2)
        self.assertEqual(CartItem.objects.count(), 0)

    #!SECTION

    # SECTION - advanced and linked test
    # def test_add_item_with_options_and_price_delta(self):
    #     option = Option.objects.create(name="color")
    #     part_model = PartModel.objects.create()
    #     part_model_option = PartModelOption.objects.create(
    #         name="blue_irridescent", part_model_id=uuid4(), code="BI", option=option, price_delta=50
    #     )

    #     dto = createCartItemDTO(
    #         cart_id=self.cart.uuid,
    #         product_id=self.product.uuid,
    #         quantity=1,
    #         part_model_option_ids=[part_model_option.uuid],
    #     )

    #     item = CartItemService.add_item(dto)

    #     self.assertEqual(item.unit_price, 150)

    #     self.assertEqual(len(item.config_snapshot["options"]), 1)

    #     option_snapshot = item.config_snapshot["options"][0]

    #     self.assertEqual(option_snapshot["name"], "color")
    #     self.assertEqual(option_snapshot["value"], "blue_irridescent")
    #     self.assertEqual(option_snapshot["price_delta"], 50.0)

    def test_hash_is_stable(self):
        snapshot = [{"a": 1}, {"b": 2}]

        h1 = ConfigHashService.generate(snapshot)
        h2 = ConfigHashService.generate(snapshot)

        self.assertEqual(h1, h2)

    def test_factory_creates_item(self):
        item = CartItemFactory.get_or_create(
            cart=self.cart,
            product=self.product,
            config_hash="abc",
            snapshot={"options": []},
            total_price=100,
            quantity=1,
        )

        self.assertEqual(item.quantity, 1)

    # TODO Finir les test unitaire et verifeir le comportement de la config

    def test_price_calculation_only(self):
        product_price = 100
        options = [{"name": "color", "value": "blue", "price_delta": 50}]
        total, snapshot = CartItemConfigResolver.resolve(product_price, options)
        self.assertEqual(total, 150)

    def test_config_snapshot_agregation(self):
        product_price = 100
        options = [
            {"name": "color", "value": "blue", "price_delta": 50},
            {"name": "Materiaux", "value": "bois", "price_delta": 20},
        ]
        total, snapshot = CartItemConfigResolver.resolve(product_price, options)

        cartItem = CartItemService.add_item()
        self.assertEqual(total, 170)
