from pprint import pprint
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from uuid import uuid4

from ..models import (
    CartItem,
    Cart,
    Product,
    ProductType,
    PartModel,
    PartType,
    ProductSchema,
    ProductComponent,
    PartModelOption,
    Option,
    InstrumentModel,
    InstrumentType,
    ComponentCompatibility,
    ProductComponentChoice,
    ConfigurationResult,
    ConfigurationCondition,
    SelectableValue,
    ConfigurationRule,
)
from ..cartItem.cartItem_service import CartItemService, CartItemFactory, ConfigHashService
from ..cartItem.cartItem_dto import createCartItemDTO
from haeron_guitar_api.product_configurator.product_type_handlers import handlers
from haeron_guitar_api.product_configurator.product_component_handlers import handlers

User = get_user_model()


class CartItemServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test")
        self.cart = Cart.objects.create(user=self.user, is_active=True)

        self.product_type = ProductType.objects.create(code="bundle_dynamique")
        self.product_type_fixed = ProductType.objects.create(code="simple_product")
        self.instrument_type_guitar = InstrumentType.objects.create(name="guitar", code="G")
        self.guitar_strat = InstrumentModel.objects.create(
            name="guitar_strat", instrument_type=self.instrument_type_guitar
        )
        self.product = Product.objects.create(
            name="Guitar Custom", instrument_model=self.guitar_strat, price=100, product_type=self.product_type
        )

    # # SECTION - adding quantity
    # def test_add_item_success(self):
    #     dto = createCartItemDTO(
    #         product_id=self.product.uuid,
    #         quantity=2,
    #     )
    #     item = CartItemService.add_item(dto, user=self.user)

    #     self.assertEqual(item.quantity, 2)
    #     self.assertEqual(item.cart, self.cart)
    #     self.assertEqual(item.product, self.product)
    #     self.assertEqual(item.unit_price, 100)

    # def test_add_item_invalide_quantity(self):

    #     dto = createCartItemDTO(
    #         product_id=self.product.uuid,
    #         quantity=0,
    #     )

    #     with self.assertRaises(ValidationError):
    #         CartItemService.add_item(dto, user=self.user)

    # def test_add_item_merge_same(self):
    #     dto = createCartItemDTO(cart_id=self.cart.uuid, product_id=self.product.uuid, quantity=1)

    #     CartItemService.add_item(dto)
    #     item = CartItemService.add_item(dto)

    #     self.assertEqual(item.quantity, 2)
    #     self.assertEqual(CartItem.objects.count(), 1)

    def test_add_same_item_twice_with_config(self):
        option_color = Option.objects.create(name="color")
        option_radius = Option.objects.create(name="radius")
        part_type = PartType.objects.create(name="neck", code="NCK")
        part_model = PartModel.objects.create(name="starLight", code="STR", price=100.00, part_type=part_type)
        part_model_option1 = PartModelOption.objects.create(
            name="bleu irridescent", code="bleu", part_model=part_model, option=option_color, price_delta=50
        )
        part_model_option2 = PartModelOption.objects.create(
            name="diametre12", code="D12", part_model=part_model, option=option_radius, price_delta=20
        )
        product_schema = ProductSchema.objects.create(name="test_guitar_schema", code="test_guitar_schema")
        self.product.product_schema = product_schema
        self.product.save()
        product_component_neck = ProductComponent.objects.create(key="neck", source_type="custom_piece")
        product_component_mic = ProductComponent.objects.create(key="mic", source_type="product_choice")
        product_schema.product_components.add(product_component_mic, product_component_neck)
        component_compat_neck = ComponentCompatibility.objects.create(
            instrument_model=self.guitar_strat, part_model=part_model, component=product_component_neck
        )
        test_mic = Product.objects.create(name="test_mic", price=100, product_type=self.product_type_fixed)
        product_choice = ProductComponentChoice.objects.create(component=product_component_mic, product=test_mic)
        rule_component = ConfigurationRule.objects.create(
            name="component_rule", target_component=product_component_neck
        )
        rule_condition = ConfigurationCondition.objects.create(
            rule=rule_component, source_component=product_component_neck, source_option=option_radius, operator="eq"
        )
        selectable_value_radius = SelectableValue.objects.create(part_model_option=part_model_option2)
        selectable_value_color = SelectableValue.objects.create(part_model_option=part_model_option1)
        rule_condition.compare_values.add(selectable_value_radius)
        rule_result = ConfigurationResult.objects.create(
            rule=rule_component, target_component=product_component_neck, target_option=option_color
        )
        rule_result.target_values.add(selectable_value_color)

        self.guitar_strat.compatible_parts.add(part_model)
        dto1 = createCartItemDTO(
            product_id=self.product.uuid,
            quantity=1,
            configuration={
                "neck": {
                    "part_model_id": str(part_model.uuid),
                    "part_model_option_ids": [str(part_model_option1.uuid), str(part_model_option2.uuid)],
                },
                "mic": {"product_id": str(test_mic.uuid)},
            },
        )
        dto2 = createCartItemDTO(
            product_id=self.product.uuid,
            quantity=1,
            configuration={
                "neck": {
                    "part_model_id": str(part_model.uuid),
                    "part_model_option_ids": [str(part_model_option1.uuid), str(part_model_option2.uuid)],
                },
                "mic": {"product_id": str(test_mic.uuid)},
            },
        )

        CartItemService.add_item(dto1, user=self.user)
        item = CartItemService.add_item(dto2, user=self.user)

        print("#" * 50)
        pprint(item.config_snapshot)

        self.assertEqual(CartItem.objects.count(), 1)
        self.assertEqual(item.quantity, 2)
        # don't forget the product cost taht is 100 . so 100 for the prodcut + 100 for the part model +50 for the option bleu +20 for the radius + 100 for the mic
        self.assertEqual(item.unit_price, 370)

    #!SECTION

    # # SECTION - update quantity
    # def test_update_quantity_success(self):
    #     item = CartItem.objects.create(
    #         cart=self.cart, product=self.product, quantity=1, unit_price=100, config_hash="abs", config_snapshot={}
    #     )
    #     updated = CartItemService.update_quantity(item.uuid, 5)

    #     self.assertEqual(updated.quantity, 5)

    # def test_update_quantity_to_zero_delete(self):
    #     item = CartItem.objects.create(
    #         cart=self.cart,
    #         product=self.product,
    #         quantity=1,
    #         unit_price=100,
    #         config_hash="abs",
    #         config_snapshot={},
    #     )
    #     result = CartItemService.update_quantity(item.uuid, 0)

    #     self.assertIsNone(result)
    #     self.assertEqual(CartItem.objects.count(), 0)

    # def test_update_quantity_invalid(self):
    #     item = CartItem.objects.create(
    #         cart=self.cart, product=self.product, quantity=1, unit_price=100, config_hash="abs", config_snapshot={}
    #     )
    #     with self.assertRaises(ValidationError):
    #         CartItemService.update_quantity(item.quantity, -2)

    # def test_update_quantity_not_found(self):
    #     with self.assertRaises(ValidationError):
    #         CartItemService.update_quantity(uuid4(), 1)

    # #!SECTION

    # # SECTION - delete
    # def test_delete_item_success(self):
    #     item = CartItem.objects.create(
    #         cart=self.cart, product=self.product, quantity=1, unit_price=100, config_hash="abs", config_snapshot={}
    #     )
    #     result = CartItemService.delete_item(item.uuid)

    #     self.assertTrue(result)
    #     self.assertEqual(CartItem.objects.count(), 0)

    # def test_delete_item_not_found(self):
    #     result = CartItemService.delete_item(uuid4())
    #     self.assertFalse(result)

    # def test_delete_item_bulk_sucess(self):
    #     item1 = CartItem.objects.create(
    #         cart=self.cart, product=self.product, quantity=1, unit_price=100, config_hash="a", config_snapshot={}
    #     )
    #     item2 = CartItem.objects.create(
    #         cart=self.cart, product=self.product, quantity=1, unit_price=100, config_hash="b", config_snapshot={}
    #     )

    #     deleted = CartItemService.delete_items([item1.uuid, item2.uuid])

    #     self.assertEqual(deleted, 2)
    #     self.assertEqual(CartItem.objects.count(), 0)

    # #!SECTION

    # def test_hash_is_stable(self):
    #     snapshot = [{"a": 1}, {"b": 2}]

    #     h1 = ConfigHashService.generate(snapshot)
    #     h2 = ConfigHashService.generate(snapshot)

    #     self.assertEqual(h1, h2)

    # def test_factory_creates_item(self):
    #     item = CartItemFactory.get_or_create(
    #         cart=self.cart,
    #         product=self.product,
    #         config_hash="abc",
    #         snapshot={"options": []},
    #         total_price=100,
    #         quantity=1,
    #     )

    #     self.assertEqual(item.quantity, 1)
