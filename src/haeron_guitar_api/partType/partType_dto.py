from dataclasses import dataclass
from typing import Optional, List
from uuid import UUID

@dataclass
class CreatePartTypeDTO:
    name:str
    code:str
    instrument_Types: Optional[List[UUID]] 

