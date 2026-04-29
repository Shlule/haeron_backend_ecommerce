from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class createCartItemDTO:
    cart_id: UUID
    product_id: UUID
    quantity: int = 1

    part_model_id: Optional[UUID] = None
    part_model_option_ids: Optional[UUID] = None
