import strawberry
from uuid import UUID
from typing import Optional


@strawberry.input
class CreatePartInput:
    part_model_id: UUID
    factory_id: UUID
    instrument_type_id: UUID
    owner_id: Optional[UUID] = None
    auth_key: Optional[str] = ""
    is_master: bool = False


@strawberry.input
class UpdatePartInput:
    serial_number: strawberry.Maybe[str] = strawberry.UNSET
    auth_key: strawberry.Maybe[str] = strawberry.UNSET
    part_model_id: strawberry.Maybe[UUID] = strawberry.UNSET
    owner_id: strawberry.Maybe[UUID] = strawberry.UNSET
    is_master: strawberry.Maybe[bool] = strawberry.UNSET
