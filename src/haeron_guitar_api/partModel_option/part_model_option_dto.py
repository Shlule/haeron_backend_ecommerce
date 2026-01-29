from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from decimal import Decimal

@dataclass
class CreatePartModelOptionDTO:
    part_model: str
    option: str
    price_delta: Optional[float] = 0.0

@dataclass
class UpdatePartModelOptionDTO:
    uuid: UUID
    price_delta: Optional[Decimal] = None