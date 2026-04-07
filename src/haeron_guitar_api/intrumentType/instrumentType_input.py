import strawberry
from typing import Optional, List
from uuid import UUID


@strawberry.input
class CreateInstrumentTypeInput:
    code: str
    name: str
    part_types: Optional[List[UUID]] = None
