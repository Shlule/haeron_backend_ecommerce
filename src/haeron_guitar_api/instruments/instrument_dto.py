from .instrument_input import *
from dataclasses import dataclass
import strawberry
 
@dataclass(slots=True)
class CreateInstrumentDTO:
    instrument_type_id: UUID
    master_part_id: UUID
    parts_id: Optional[List[UUID]]
    owner_id: Optional[UUID] = None

@dataclass(slots=True)
class UpdateInstrumentDTO:
    instrument_id: UUID
    parts_ids: Optional[List[UUID]] = None
    owner_id: Optional[UUID] = None


