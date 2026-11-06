from typing import Optional
from uuid import UUID

import strawberry
from django.core.exceptions import ValidationError
from strawberry.scalars import JSON

from .storefront_input import AddToCartInput
from .storefront_service import StorefrontService


# public queries used by the shop (no authentication needed for a visitor)


def _user(info):
    return getattr(info.context["request"], "user", None)


def _error_message(error):
    messages = getattr(error, "messages", None)
    if messages:
        return " ".join(str(m) for m in messages)
    return str(error)


@strawberry.type
class StorefrontQuery:
    @strawberry.field
    def shop_products(self) -> JSON:
        return StorefrontService.products()

    @strawberry.field
    def shop_cart(self, info: strawberry.Info, cart_key: Optional[str] = None) -> JSON:
        cart = StorefrontService.find_cart(user=_user(info), cart_key=cart_key)
        return StorefrontService.serialize(cart, cart_key if cart else None)


@strawberry.type
class StorefrontMutation:
    @strawberry.mutation
    def add_to_cart(self, info: strawberry.Info, input: AddToCartInput) -> JSON:
        if input.quantity < 1 or input.quantity > 20:
            raise Exception("La quantité doit être comprise entre 1 et 20.")
        try:
            cart, cart_key = StorefrontService.add(
                input.product_id, input.configuration, input.quantity, user=_user(info), cart_key=input.cart_key
            )
        except (ValidationError, ValueError) as error:
            raise Exception(_error_message(error)) from error
        return StorefrontService.serialize(cart, cart_key)

    @strawberry.mutation
    def remove_from_cart(self, info: strawberry.Info, item_id: UUID, cart_key: Optional[str] = None) -> JSON:
        try:
            cart = StorefrontService.remove(item_id, user=_user(info), cart_key=cart_key)
        except ValidationError as error:
            raise Exception(_error_message(error)) from error
        return StorefrontService.serialize(cart, cart_key)
