from dataclasses import dataclass, field
from typing import Optional, Any
from uuid import UUID


@dataclass
class CreatePartDTO:
    part_model_id: UUID
    factory_id: UUID
    instrument_type_id: UUID
    owner_id: Optional[UUID] = None
    is_master: bool = False
    production_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class UpdatePartDTO:
    serial_number: Optional[str] = None
    owner_id: Optional[UUID] = None
    part_model_id: Optional[UUID] = None
    is_master: Optional[bool] = None
