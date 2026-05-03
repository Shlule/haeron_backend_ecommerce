from .custom_piece_handler import CustomPieceHandler
from ..product_type_registry import ProductTypeHandlerRegistry


ProductTypeHandlerRegistry.register("custom_piece", CustomPieceHandler)
