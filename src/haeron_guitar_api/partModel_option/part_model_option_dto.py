from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from decimal import Decimal


@dataclass
class CreatePartModelOptionDTO:
    name: str
    code: Optional[str]
    part_model: UUID
    option: UUID
    price_delta: Optional[float] = 0.0


@dataclass
class UpdatePartModelOptionPriceDTO:
    uuid: UUID
    price_delta: Optional[Decimal] = None
