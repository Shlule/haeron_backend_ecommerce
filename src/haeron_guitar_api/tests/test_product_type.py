from unittest import TestCase
from uuid import uuid4
from ..models import ProductType

from ..product_configurator.product_type_handlers.product_type_registry import ProductTypeHandlerRegistry
from ..product_configurator.product_component_handlers.handlers.custom_piece_handler import CustomPieceHandler


class Test_ProductTypeHandlerRegistry(TestCase):
    def setUp(self):
        self.product_type = ProductType.objects.create(code="custom_piece")

    def test_registry_retrieve_success(self):
        test = ProductTypeHandlerRegistry.get_handler(self.product_type.code)
        self.assertEqual(type(test), CustomPieceHandler)

    def test_registry_no_handler(self):
        with self.assertRaises(ValueError):
            ProductTypeHandlerRegistry.get_handler(uuid4())
