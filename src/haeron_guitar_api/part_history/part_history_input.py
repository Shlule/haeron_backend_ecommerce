import strawberry
from uuid import UUID

@strawberry.input
class CreatePartHistoryInput:
    description: str
    title: str
    event_type: str
    part: UUID
    

@strawberry.input
class UpdatePartHistoryInput:
    title: strawberry.Maybe[str] = strawberry.UNSET
    event_type: strawberry.Maybe[str] = strawberry.UNSET
    description: strawberry.Maybe[str] = strawberry.UNSET
    part: strawberry.Maybe[UUID] = strawberry.UNSET