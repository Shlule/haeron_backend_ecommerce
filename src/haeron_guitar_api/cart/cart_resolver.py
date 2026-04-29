from ast import List
from typing import Optional
from uuid import UUID
import strawberry
from .cart_input import CartFilterInput, CreateCartInput, MergeCartInput
from .cart_dto import CreateCartDTO
from .cart_filter import CartFilterSet
from .cart_service import CartService
from ..models import Cart
from ..types import CartGQLType


@strawberry.type
class CartQuery:
    @strawberry.field
    def cart(self, filters: Optional[CartFilterInput]) -> List[CartGQLType]:
        qs = Cart.objects.all()
        if filters:
            filter_dict = {k: v for k, v in filters.__dict__.items() if v is not None}
            qs = CartFilterSet(filter_dict, queryset=qs).qs
        return qs


@strawberry.type
class CartMutation:
    @strawberry.mutation
    def create_cart(self, input: CreateCartInput) -> CartGQLType:
        dto = CreateCartDTO(
            session_key=input.session_key,
            user=input.user,
        )
        if not dto:
            return None
        cart = CartService.get_or_create_cart(dto)
        return cart

    @strawberry.mutation
    def merge_guest_cart(self, input: MergeCartInput, info) -> CartGQLType:
        user = info.context.request.user
        guest_cart = Cart.objects.get(pk=input.guest_cart_id)

        cart = CartService.merge_guest_to_user(guest_cart=guest_cart, user=user)
        return cart

    @strawberry.mutation
    def delete_cart(self, cart_id: UUID) -> bool:
        Cart.objects.get(pk=cart_id).delete()
        return True
