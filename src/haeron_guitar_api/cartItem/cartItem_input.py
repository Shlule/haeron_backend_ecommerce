import strawberry

from typing import Any, Optional, Dict
from uuid import UUID


@strawberry.input
class CartItemFilterInput:
    id: Optional[UUID] = None
    cart_id: Optional[UUID] = None
    product_id: Optional[UUID] = None


@strawberry.input
class CreateCartItemsInput:
    product_id: UUID
    quantity: int = 1
    configuration: Dict[str, Any]
