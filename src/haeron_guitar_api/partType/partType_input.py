import strawberry
from typing import Optional, List
from uuid import UUID


@strawberry.input
class PartTypeFilterInput:
    id: Optional[str] = None
    name: Optional[str] = None
    code: Optional[str] = None


@strawberry.input
class CreatePartTypeInput:
    code: str
    name: str
    intrument_types: Optional[List[UUID]] = None
