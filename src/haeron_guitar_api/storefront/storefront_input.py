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


@strawberry.input
class UpdateCartItemInput:
    item_id: UUID
    # new quantity and / or new configuration (the line is checked and priced again)
    quantity: Optional[int] = None
    configuration: Optional[JSON] = None
    cart_key: Optional[str] = None


@strawberry.input
class PlaceOrderInput:
    # generated once by the checkout page : sending it twice gives back the same order
    idempotency_key: UUID
    email: str
    first_name: str
    last_name: str
    address: str
    postal_code: str
    city: str
    country: str = "FR"
    phone: str = ""
    cart_key: Optional[str] = None
