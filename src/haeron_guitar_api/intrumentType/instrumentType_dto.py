from dataclasses import dataclass
from typing import Optional, List
from uuid import UUID


@dataclass(slots=True)
class CreateInstrumentTypeDTO:
    name: str
    code: str
    part_types: Optional[List[UUID]] = None
