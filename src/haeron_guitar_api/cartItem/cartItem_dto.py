from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from typing import Dict, Any


@dataclass
class createCartItemDTO:
    cart_id: UUID
    product_id: UUID
    configuration: Optional[Dict[str, Any]] = None
    quantity: int = 1
