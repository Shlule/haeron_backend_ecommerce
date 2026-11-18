from typing import Optional
from uuid import UUID

import strawberry
from django.core.exceptions import ValidationError
from strawberry.scalars import JSON

from ..checkout.checkout_dto import CustomerDTO
from ..payments.payment_service import PaymentService
from .storefront_input import AddToCartInput, PlaceOrderInput, UpdateCartItemInput
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

    @strawberry.field
    def shop_order(self, order_id: UUID) -> Optional[JSON]:
        order = StorefrontService.find_order(order_id)
        return StorefrontService.serialize_order(order) if order else None


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

    @strawberry.mutation
    def update_cart_item(self, info: strawberry.Info, input: UpdateCartItemInput) -> JSON:
        try:
            cart = StorefrontService.update(
                input.item_id, input.quantity, input.configuration, user=_user(info), cart_key=input.cart_key
            )
        except (ValidationError, ValueError) as error:
            raise Exception(_error_message(error)) from error
        return StorefrontService.serialize(cart, input.cart_key)

    @strawberry.mutation
    def place_order(self, info: strawberry.Info, input: PlaceOrderInput) -> JSON:
        customer = CustomerDTO(
            email=input.email,
            first_name=input.first_name,
            last_name=input.last_name,
            address=input.address,
            postal_code=input.postal_code,
            city=input.city,
            country=input.country,
            phone=input.phone,
        )
        try:
            order = StorefrontService.checkout(input.idempotency_key, customer, user=_user(info), cart_key=input.cart_key)
        except (ValidationError, ValueError) as error:
            raise Exception(_error_message(error)) from error
        return StorefrontService.serialize_order(order)

    @strawberry.mutation
    def pay_order(self, order_id: UUID) -> str:
        """Url of the Stripe page where the customer pays the order."""
        try:
            return PaymentService.start_checkout(order_id)
        except ValidationError as error:
            raise Exception(_error_message(error)) from error

    @strawberry.mutation
    def confirm_order_payment(self, order_id: UUID, session_id: str) -> JSON:
        """Customer back from Stripe : the payment is checked with Stripe, then the order is returned."""
        try:
            order = PaymentService.confirm_checkout(order_id, session_id)
        except ValidationError as error:
            raise Exception(_error_message(error)) from error
        return StorefrontService.serialize_order(order)
