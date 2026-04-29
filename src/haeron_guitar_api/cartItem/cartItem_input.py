import strawberry

from typing import Optional, List
from uuid import UUID


@strawberry.input
class CartItemFilterInput:
    id: Optional[UUID] = None
    cart_id: Optional[UUID] = None
    product_id: Optional[UUID] = None


@strawberry.input
class CreateCartItemsInput:
    cart_id: UUID
    product_id: UUID
    quantity: int = 1
    part_model_id: Optional[UUID] = None
    part_model_option_ids: Optional[List[UUID]] = None
