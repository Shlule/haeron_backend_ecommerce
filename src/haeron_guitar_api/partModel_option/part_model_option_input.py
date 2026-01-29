import strawberry
from decimal import Decimal
from typing import Optional
from uuid import UUID

@strawberry.input
class CreatePartModelOptionInput:
    part_model: str
    option: str
    price_delta: float

@strawberry.input
class UpdatePartModelOptionInput:
    uuid: UUID
    price_delta: Optional[Decimal] = None