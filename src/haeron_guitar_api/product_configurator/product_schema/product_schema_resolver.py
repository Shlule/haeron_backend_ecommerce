import strawberry
from uuid import UUID
from ..models import Product
from ..types.product_configurator_types import ProductConfiguration
from authUser.permission.permission import HasRole, IsAuthenticated

@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated, HasRole("superadmin","admin", "rnd")])
    def product_configuration(self, product_id: UUID) -> "ProductConfiguration":
        product = (
            Product.objects.select_related("product_schema")
            .prefetch_related("product_schema__product_components")
            .get(pk=product_id)
        )
        return
