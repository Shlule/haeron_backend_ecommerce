import strawberry
from typing import Optional, List
from uuid import UUID


# @strawberry.input
# class InstrumentType:
#     serial_number: str
#     main_part_id: strawberry.ID
#     owner_id: Optional[strawberry.ID] = None
#     part_ids: List[strawberry.ID] = None

#TODO penser a faire de la double auth avec un facature officiel pour le changement du nfc et de yubikey
@strawberry.input
class CreateInstrumentInput:
    instrument_type_id: strawberry.ID
    owner_id: Optional[strawberry.ID] = None
    master_part_id: UUID
    parts_id: Optional[List[UUID]] = None

@strawberry.input
class UpdateInstrumentInput:
    instrument_id: strawberry.ID
    parts_id: strawberry.Maybe[List[strawberry.ID] | None] = None
    owner_id: strawberry.Maybe[strawberry.ID | None] = None

