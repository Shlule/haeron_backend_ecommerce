import strawberry
from uuid import UUID
from typing import List, Optional
from decimal import Decimal


@strawberry.input
class CreatePartModelInput:
    name: str
    part_type_id: UUID
    series_id: Optional[UUID] = None
    price: Optional[Decimal] = 0.0
    code: Optional[str] = None


@strawberry.input
class UpdatePartModelInput:
    uuid: UUID
    name: strawberry.Maybe[str] = strawberry.UNSET
    part_type_id: strawberry.Maybe[UUID] = strawberry.UNSET
    code: strawberry.Maybe[str] = strawberry.UNSET
    price: strawberry.Maybe[Decimal] = strawberry.UNSET
    series_id: strawberry.Maybe[UUID] = strawberry.UNSET
    status: strawberry.Maybe[str] = strawberry.UNSET
