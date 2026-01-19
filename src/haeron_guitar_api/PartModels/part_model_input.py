import strawberry
from uuid import UUID
from typing import List, Optional
from decimal import Decimal

@strawberry.input
class CreatePartModelInput:
    name: str
    part_type_id: UUID
    series_id: Optional[UUID] = None
    compatibles_options_ids: Optional[List[UUID]] = None
    price: Optional[Decimal] = 0.0
    code: Optional[str] = None

@strawberry.input
class UpdatePartModelInput:
    uuid: UUID
    name: strawberry.Maybe[str|None] = None
    part_type_id: strawberry.Maybe[UUID|None] = None
    code: strawberry.Maybe[str|None] = None
    price: strawberry.Maybe[Decimal|None] = None
    series_id: strawberry.Maybe[UUID|None] = None
    compatibles_options_ids: strawberry.Maybe[List[UUID]|None] = None