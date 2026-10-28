from django.core.exceptions import ValidationError

from ..product_type_registry import ProductTypeHandlerRegistry


@ProductTypeHandlerRegistry.register("bundle_static")
class BundleStaticHandler:
    """
    Bundle statique = composants fixés dans le schema,
    aucun input front requis.
    """

    def resolve(self, product, config=None, **kwargs):
        components = product.product_schema.product_components.all()

        snapshot = []
        total_price = 0

        for component in components:
            if component.source_type != "fixed":
                raise ValidationError(f"Bundle static cannot contain dynamic component: {component.key}")

            fixed = component.fixed_product

            snapshot.append(
                {
                    "component": component.key,
                    "product_id": str(fixed.uuid),
                    "name": fixed.name,
                    "price": float(fixed.price),
                }
            )

            total_price += float(fixed.price)

        return {
            "type": "bundle_static",
            "product_id": str(product.uuid),
            "items": snapshot,
            "price": total_price,
        }, total_price
