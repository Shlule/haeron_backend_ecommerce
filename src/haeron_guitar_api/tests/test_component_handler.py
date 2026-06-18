from django.test import TestCase
from uuid import uuid4
from ..models import ProductType

from ..product_configurator.product_component_handlers.product_component_registry import ComponentHandlerRegistry
from ..product_configurator.product_component_handlers.handlers.custom_piece_handler import CustomPieceHandler
from ..product_configurator.product_component_handlers import handlers


class Test_ComponentHandlerRegistry(TestCase):
    def setUp(self):
        self.product_type = ProductType.objects.create(code="custom_piece")

    def test_registry_retrieve_success(self):
        test = ComponentHandlerRegistry.get_handler(self.product_type.code)
        self.assertEqual(type(test), CustomPieceHandler)

    def test_registry_no_handler(self):
        with self.assertRaises(ValueError):
            ComponentHandlerRegistry.get_handler(uuid4())
