from dataclasses import dataclass
from typing import Optional
from uuid import UUID

@dataclass
class CreatePartDTO:
    serial_number: str
    auth_key: str
    part_model_id: UUID
    owner_id: Optional[UUID] = None
    is_master: bool = False
    
@dataclass
class UpdatePartDTO:
    serial_number: Optional[str] = None
    owner_id: Optional[UUID] = None
    part_model_id: Optional[UUID] = None
    is_master: Optional[bool] = None