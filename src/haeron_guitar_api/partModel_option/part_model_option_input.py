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
class PartModelOptionInputFilter:
    id: Optional[str] = None
    name: Optional[str] = None
    option: Optional[str] = None
    option_name: Optional[str] = None
    option_category: Optional[str] = None
    partModel: Optional[str] = None
    partModel_name: Optional[str] = None
    partModel_Code: Optional[str] = None


@strawberry.input
class UpdatePartModelOptionPriceInput:
    uuid: UUID
    price_delta: Optional[Decimal] = None
