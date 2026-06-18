from uuid import UUID
import strawberry
from typing import Optional, List

from .cartItem_service import CartItemService
from .cartItem_dto import createCartItemDTO
from .cartItem_input import CreateCartItemsInput, CartItemFilterInput
from .cartItem_filter import CartItemFilterSet
from ..models import CartItem

from ..types.types import CartItemGQLType


@strawberry.type
class CartItemQuery:
    @strawberry.field
    def cart_items(self, filters: CartItemFilterInput) -> List[CartItemGQLType]:
        qs = CartItem.objects.all()
        if filters:
            filter_dict = {k: v for k, v in filters.__dict__.items() if v is not None}
            qs = CartItemFilterInput(filter_dict, queryset=qs).qs
        return qs


@strawberry.type
class CartItemMutation:
    @strawberry.mutation
    def create_cart_item(self, input: CreateCartItemsInput) -> CartItemGQLType:
        dto = createCartItemDTO(
            configuration=input.configuration,
            product_id=input.product_id,
            quantity=input.quantity,
        )

        item = CartItemService.add_item(dto, user=info.context.user, session_key=info.context.session.session_key)
        return item

    @strawberry.mutation
    def set_quantity(self, cart_item_id: UUID, quantity: int) -> CartItemGQLType:
        item = CartItem.objects.select_related("cart").get(pk=cart_item_id)
        if quantity <= 0:
            return None
        item.quantity = quantity
        item.save()
        return item

    @strawberry.mutation
    def delete_cart_item(self, cart_item_id: UUID) -> bool:
        CartItem.objects.get(pk=cart_item_id).delete()
        return True
