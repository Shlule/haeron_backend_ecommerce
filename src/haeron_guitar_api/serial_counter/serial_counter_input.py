import strawberry
from typing import Optional
from uuid import UUID
from datetime import date


@strawberry.input
class SerialCounterFilterInput:
    factory_id: Optional[UUID] = None
    date: Optional["date"] = None
    date_after: Optional["date"] = None
    date_before: Optional["date"] = None
