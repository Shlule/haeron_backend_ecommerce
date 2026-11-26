"""Products of the shop seen from the back-office : the list, a new ready-to-order product, and hiding or showing one.

A configurable guitar needs a schema and its components (see the "Données" pages), a piece sold alone is made by
PieceProductBuilder ; here are the products sold as they are (strap, strings, case...).
"""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models import Count

from ..models import Product, ProductType

SIMPLE_TYPE = "simple"


def _text(value):
    return (value or "").strip()


def with_kind(products):
    """Annotates what is needed by kind_of : number of steps, and in how many templates the steps are used."""
    return products.annotate(
        component_count=Count("product_schema__product_components", distinct=True),
        schema_count=Count("product_schema__product_components__product_schemas", distinct=True),
    )


def kind_of(product):
    """simple : sold as it is ; piece : one step shared with a guitar (a piece sold alone) ; configurable : the rest.
    A new guitar with a single step of its own is still configurable."""
    if product.product_schema_id is None:
        return "simple"
    return "piece" if product.component_count == 1 and product.schema_count > 1 else "configurable"


class ProductCatalogue:
    @staticmethod
    def serialize(product):
        return {
            "id": str(product.uuid),
            "name": product.name,
            "price": float(product.price),
            "type": product.product_type.code,
            # simple : sold as it is ; configurable : a guitar in the configurator ; piece : one piece of a guitar
            "kind": kind_of(product),
            "visible": product.is_visible,
            "image": product.image,
            "model3d": product.model_3d,
            "instrumentModel": product.instrument_model.name if product.instrument_model_id else None,
        }

    @staticmethod
    def _products():
        return with_kind(Product.objects.select_related("product_type", "instrument_model"))

    @staticmethod
    def products():
        return [ProductCatalogue.serialize(p) for p in ProductCatalogue._products().order_by("name")]

    @staticmethod
    def _price(value):
        try:
            price = Decimal(str(value if value is not None else 0))
        except InvalidOperation as error:
            raise ValidationError("Prix invalide.") from error
        if price < 0:
            raise ValidationError("Le prix ne peut pas être négatif.")
        return price

    @staticmethod
    def create(data):
        """A product sold as it is : {name, price, image, visible}."""
        name = _text(data.get("name"))
        if not name:
            raise ValidationError("Donne un nom au produit.")
        if Product.objects.filter(name__iexact=name).exists():
            raise ValidationError(f"Un produit s'appelle déjà « {name} ».")
        product_type, _ = ProductType.objects.get_or_create(code=SIMPLE_TYPE)
        product = Product.objects.create(
            name=name,
            price=ProductCatalogue._price(data.get("price")),
            product_type=product_type,
            image=_text(data.get("image")),
            is_visible=bool(data.get("visible", True)),
        )
        return ProductCatalogue.serialize(ProductCatalogue._products().get(pk=product.pk))

    @staticmethod
    def set_visible(product_id, visible):
        if not Product.objects.filter(pk=product_id).update(is_visible=visible):
            raise ValidationError("Produit introuvable.")
        return ProductCatalogue.serialize(ProductCatalogue._products().get(pk=product_id))
