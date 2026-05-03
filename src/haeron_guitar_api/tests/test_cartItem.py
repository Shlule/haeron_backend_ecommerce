import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from uuid import uuid4

from ..models import CartItem, Cart, Product, ProductType, PartModel, PartType, PartModelOption, Option
from ..cartItem.cartItem_service import CartItemService, CartItemFactory, ConfigHashService
from ..cartItem.cartItem_dto import createCartItemDTO

User = get_user_model()


class CartItemServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test")
        self.cart = Cart.objects.create(user=self.user, is_active=True)
        self.product_type = ProductType.objects.create(code="custom_piece")
        self.product = Product.objects.create(name="Guitar Custom", price=100, product_type=self.product_type)

    # SECTION - adding quantity
    def test_add_item_success(self):
        dto = createCartItemDTO(
            cart_id=self.cart.uuid,
            product_id=self.product.uuid,
            quantity=2,
        )
        item = CartItemService.add_item(dto)

        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.cart, self.cart)
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.unit_price, 100)

    def test_add_item_invalide_quantity(self):

        dto = createCartItemDTO(
            cart_id=self.cart.uuid,
            product_id=self.product.uuid,
            quantity=0,
        )

        with self.assertRaises(ValidationError):
            CartItemService.add_item(dto)

    def test_add_item_merge_same(self):
        dto = createCartItemDTO(cart_id=self.cart.uuid, product_id=self.product.uuid, quantity=1)

        CartItemService.add_item(dto)
        item = CartItemService.add_item(dto)

        self.assertEqual(item.quantity, 2)
        self.assertEqual(CartItem.objects.count(), 1)

    def test_add_same_item_twice_with_config(self):
        # TODO -  make the creat
        option = Option.objects.create(name="color")
        part_type = PartType.objects.create(name="superior body", code="SB")
        part_model = PartModel.objects.create(name="starLight", code="STR", price=100.00, part_type=part_type)
        part_model_option1 = PartModelOption.objects.create(
            name="bleu irridescent", code="bleu", part_model=part_model, option=option, price_delta=50
        )
        part_model_option2 = PartModelOption.objects.create(
            name="rouge vermillion", code="rouge", part_model=part_model, option=option, price_delta=20
        )

        dto1 = createCartItemDTO(
            cart_id=self.cart.uuid,
            product_id=self.product.uuid,
            quantity=1,
            configuration={
                "part_model_id": str(part_model.uuid),
                "part_model_option_ids": [str(part_model_option1.uuid), str(part_model_option2.uuid)],
            },
        )
        dto2 = createCartItemDTO(
            cart_id=self.cart.uuid,
            product_id=self.product.uuid,
            quantity=1,
            configuration={
                "part_model_id": str(part_model.uuid),
                "part_model_option_ids": [str(part_model_option1.uuid), str(part_model_option2.uuid)],
            },
        )

        CartItemService.add_item(dto1)
        item = CartItemService.add_item(dto2)

        self.assertEqual(CartItem.objects.count(), 1)
        self.assertEqual(item.quantity, 2)
        # don't forget the product cost taht is 100 . so 100 + 100 +50+20
        self.assertEqual(item.unit_price, 270)

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
            cart=self.cart,
            product=self.product,
            quantity=1,
            unit_price=100,
            config_hash="abs",
            config_snapshot={},
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
