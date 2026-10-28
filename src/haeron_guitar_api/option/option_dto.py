from dataclasses import dataclass
from typing import Optional

@dataclass
class CreateOptionDTO:
    name: str
    description: Optional[str]
