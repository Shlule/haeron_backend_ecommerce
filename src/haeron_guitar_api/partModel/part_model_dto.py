from dataclasses import dataclass
from uuid import UUID
from decimal import Decimal
from typing import List, Optional


@dataclass
class CreatePartModelDTO:
    name: str
    part_type_id: UUID
    series_id: Optional[UUID] = None
    price: Decimal = 0.0
    code: Optional[str] = None


@dataclass
class UpdatePartModelDTO:
    name: Optional[str | None] = None
    part_type_id: Optional[UUID | None] = None
    price: Optional[Decimal | None] = None
    code: Optional[str | None] = None
