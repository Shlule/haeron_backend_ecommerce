from typing import Optional
from uuid import UUID

import strawberry
from strawberry.scalars import JSON


@strawberry.input
class AddToCartInput:
    product_id: UUID
    # configuration built by the configurator, {} for a product that is not configurable
    configuration: Optional[JSON] = None
    quantity: int = 1
    # key of the visitor cart, returned by the first addToCart (not needed for a logged in user)
    cart_key: Optional[str] = None
