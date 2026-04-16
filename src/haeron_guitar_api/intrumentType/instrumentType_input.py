import strawberry
from typing import Optional, List
from uuid import UUID


@strawberry.input
class InstrumentTypeFilterInput:
    id: Optional[str] = None
    name: Optional[str] = None
    code: Optional[str] = None


@strawberry.input
class CreateInstrumentTypeInput:
    code: str
    name: str
    part_types: Optional[List[UUID]] = None
