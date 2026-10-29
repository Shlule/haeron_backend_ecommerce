import json
import strawberry
from uuid import UUID
from strawberry.scalars import JSON

from ..models import Product
from .builder import build_product_configuration
from .configuration_normalizer import ConfigurationNormalizer
from .configuration_rule_engine import RuleEngine
from .product_type_handlers.product_type_registry import ProductTypeHandlerRegistry

# the registries are filled when the handlers modules are imported
from .product_component_handlers import handlers as _component_handlers  # noqa: F401
from .product_type_handlers import handlers as _product_type_handlers  # noqa: F401


# public queries used by the front end configurator (no authentication needed for a shop visitor)


def _get_product(product_id):
    return (
        Product.objects.select_related("product_type", "product_schema", "instrument_model")
        .prefetch_related("product_schema__product_components")
        .get(pk=product_id)
    )


def _error_message(error):
    messages = getattr(error, "messages", None)
    if messages:
        return " ".join(str(m) for m in messages)
    return str(getattr(error, "message", error))


def build_configurator_template(product):
    engine = RuleEngine()
    configuration = build_product_configuration(product)
    rules = engine.collect_rules(product)["rules"]

    return {
        "product": {
            "id": str(product.uuid),
            "name": product.name,
            "price": float(product.price),
            "type": product.product_type.code,
        },
        "components": configuration.components,
        "rules": [engine.serialize_rule_json(rule) for rule in rules],
    }


def validate_configuration(product, configuration: dict):
    """Same validation as the cart (handlers + rule engine) but without creating a CartItem"""
    result = {"valid": False, "total_price": None, "snapshot": [], "errors": [], "violations": []}

    handler = ProductTypeHandlerRegistry.get_handler(product.product_type.code)
    if not handler:
        result["errors"].append(f"No handler exist for the product type {product.product_type.code}")
        return result

    try:
        snapshot, total_price = handler.resolve(product, configuration or {})
    except Exception as error:
        result["errors"].append(_error_message(error))
        return result

    engine = RuleEngine()
    rules = [engine.serialize_rule(rule) for rule in engine.collect_rules(product)["rules"]]
    violations = engine.check(configuration=ConfigurationNormalizer.normalize(snapshot), rules=rules)

    snapshot = snapshot if isinstance(snapshot, list) else [snapshot]
    # some handlers return Decimal prices
    result["snapshot"] = json.loads(json.dumps(snapshot, default=str))
    result["total_price"] = float(total_price)
    result["violations"] = violations
    result["valid"] = not violations
    return result


@strawberry.type
class ConfiguratorQuery:
    @strawberry.field
    def configurator_products(self) -> JSON:
        products = Product.objects.select_related("product_type").filter(
            product_type__code="bundle_dynamique", product_schema__isnull=False
        )
        return [
            {"id": str(p.uuid), "name": p.name, "price": float(p.price), "type": p.product_type.code}
            for p in products
        ]

    @strawberry.field
    def configurator_template(self, product_id: UUID) -> JSON:
        return build_configurator_template(_get_product(product_id))

    @strawberry.field
    def validate_configuration(self, product_id: UUID, configuration: JSON) -> JSON:
        return validate_configuration(_get_product(product_id), configuration)
