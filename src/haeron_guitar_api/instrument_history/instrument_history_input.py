import strawberry
from uuid import UUID

@strawberry.input
class CreateInstrumentHistoryInput: 
    description: str
    title: str
    event_type: str
    instrument: UUID


@strawberry.input
class UpdateInstrumentHistoryInput:
    title: strawberry.Maybe[str] = strawberry.UNSET
    event_type: strawberry.Maybe[str] = strawberry.UNSET
    description: strawberry.Maybe[str] = strawberry.UNSET
    instrument: strawberry.Maybe[UUID] = strawberry.UNSET
