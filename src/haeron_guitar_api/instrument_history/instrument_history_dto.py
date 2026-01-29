from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from decimal import Decimal

@dataclass
class CreateInstrumentHistoryDTO:
    description: str
    title: str
    event_type: str
    instrument: UUID

@dataclass
class UpdateInstrumentHistoryDTO:
    description: Optional[str] = None
    title: Optional[str] = None
    event_type: Optional[str] = None
    instrument: Optional[UUID] = None

    