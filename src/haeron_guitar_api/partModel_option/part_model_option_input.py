import strawberry
from decimal import Decimal
from typing import Optional
from uuid import UUID


@strawberry.input
class CreatePartModelOptionInput:
    name: str
    code: Optional[UUID]
    part_model: UUID
    option: UUID
    price_delta: float


@strawberry.input
class UpdatePartModelOptionPriceInput:
    uuid: UUID
    price_delta: Optional[Decimal] = None
