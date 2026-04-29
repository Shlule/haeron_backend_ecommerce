from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class CreateCartDTO:
    user: Optional[UUID] = None
    session_key: Optional[str] = None
