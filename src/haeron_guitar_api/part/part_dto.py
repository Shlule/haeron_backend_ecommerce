from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class CreatePartDTO:
    part_model_id: UUID
    factory_id: UUID
    instrument_type_id: UUID
    owner_id: Optional[UUID] = None
    auth_key: Optional[str] = ""
    is_master: bool = False


@dataclass
class UpdatePartDTO:
    serial_number: Optional[str] = None
    owner_id: Optional[UUID] = None
    part_model_id: Optional[UUID] = None
    is_master: Optional[bool] = None
