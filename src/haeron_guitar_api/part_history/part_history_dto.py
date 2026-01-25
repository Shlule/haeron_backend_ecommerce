from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from decimal import Decimal

@dataclass
class CreatePartHistoryDTO:
    description: str
    title: str
    event_type: str
    part: UUID

@dataclass
class UpdatePartHistoryDTO:
    description: Optional[str] = None
    title: Optional[str] = None
    event_type: Optional[str] = None
    part: Optional[UUID] = None