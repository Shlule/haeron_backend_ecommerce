import strawberry
from uuid import UUID
from typing import Optional
    
@strawberry.input
class CreatePartInput: 
    serial_number: str
    auth_key: str
    part_model_id: UUID
    owner_id: Optional[UUID] = None
    is_master: bool = False

@strawberry.input
class UpdatePartInput:
    serial_number: strawberry.Maybe[str] = strawberry.UNSET
    auth_key: strawberry.Maybe[str] = strawberry.UNSET
    part_model_id: strawberry.Maybe[UUID] = strawberry.UNSET
    owner_id: strawberry.Maybe[UUID] = strawberry.UNSET
    is_master: strawberry.Maybe[bool] = strawberry.UNSET