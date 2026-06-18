import strawberry
from haeron_guitar_api.types.types import OrderGQLType
from .checkout_service import CheckoutService


@strawberry.type
class CheckoutMutation:
    @strawberry.mutation
    def checkout(self, info: strawberry.Info) -> OrderGQLType:
        return CheckoutService.checkout(
            user=info.context.request.user,
            session_key=info.context.request.session.session_key,
        )


CheckoutMutation = CheckoutMutation
