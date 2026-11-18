"""Products that sell one piece of an instrument on its own (a Starlight body, a neck...), through the configurator.

A piece product gets its own schema holding the component of the guitar it comes from : a component can be shared
by several schemas, so the piece keeps the same part models, options, prices and rules as in the guitar, and a
change made to the component in the catalogue shows in both. The rules that need another piece of the guitar
do not apply : that piece is not in the configuration.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.utils.text import slugify

from ..models import ComponentCompatibility, InstrumentModel, Product, ProductComponent, ProductSchema, ProductType
from .product_catalogue import with_kind

PRODUCT_TYPE = "bundle_dynamique"


def _text(value):
    return (value or "").strip()


class PieceProductBuilder:
    @staticmethod
    def _piece_products():
        """Products whose schema holds a single component : {(instrument model id, component id): product}."""
        products = (
            with_kind(Product.objects.filter(product_schema__isnull=False))
            .filter(component_count=1, schema_count__gt=1)
            .prefetch_related("product_schema__product_components")
        )
        return {
            (product.instrument_model_id, product.product_schema.product_components.all()[0].pk): product
            for product in products
        }

    @staticmethod
    def form_data():
        """For each instrument model : its configurable pieces (components of type custom_piece), the part models
        each one offers, and the product already selling it alone if there is one.
        The image and 3D model of the complete instrument are given to fill the new products."""
        # steps of a complete instrument (a template with several steps), not of a piece already sold alone
        guitar_schemas = ProductSchema.objects.annotate(step_count=Count("product_components")).filter(step_count__gt=1)
        compatibilities = (
            ComponentCompatibility.objects.filter(
                component__source_type="custom_piece",
                component__product_schemas__in=guitar_schemas,
                instrument_model__isnull=False,
                part_model__isnull=False,
            )
            .distinct()
            .select_related("component", "part_model__part_type")
            .order_by("component__key", "part_model__code")
        )
        pieces = {}
        for compatibility in compatibilities:
            by_component = pieces.setdefault(compatibility.instrument_model_id, {})
            piece = by_component.setdefault(
                compatibility.component_id, {"component": compatibility.component, "part_models": []}
            )
            piece["part_models"].append(compatibility.part_model)

        existing = PieceProductBuilder._piece_products()
        # the complete instrument sold on the shop : the product of the model with the most components
        complete = {}
        for product in Product.objects.filter(instrument_model__isnull=False, product_schema__isnull=False).annotate(
            component_count=Count("product_schema__product_components")
        ):
            current = complete.get(product.instrument_model_id)
            if product.component_count > 1 and (current is None or product.component_count > current.component_count):
                complete[product.instrument_model_id] = product

        models = InstrumentModel.objects.filter(pk__in=pieces.keys()).select_related("instrument_type").order_by("name")
        result = []
        for model in models:
            guitar = complete.get(model.pk)
            result.append(
                {
                    "id": str(model.uuid),
                    "name": model.name,
                    "instrumentType": model.instrument_type.name,
                    "product": {"id": str(guitar.uuid), "name": guitar.name} if guitar else None,
                    "image": guitar.image if guitar else "",
                    "model3d": guitar.model_3d if guitar else "",
                    "pieces": [
                        {
                            "componentId": str(component_id),
                            "key": piece["component"].key,
                            "partModels": [
                                {
                                    "id": str(pm.uuid),
                                    "name": pm.name,
                                    "code": pm.code,
                                    "price": float(pm.price),
                                    "status": pm.status,
                                    "partType": pm.part_type.name,
                                }
                                for pm in piece["part_models"]
                            ],
                            "product": (
                                {"id": str(sold.uuid), "name": sold.name}
                                if (sold := existing.get((model.pk, component_id)))
                                else None
                            ),
                        }
                        for component_id, piece in pieces[model.pk].items()
                    ],
                }
            )
        return {"instrumentModels": result}

    @staticmethod
    def _schema_code(model, component):
        base = slugify(f"{model.name} {component.key}").replace("-", "_")[:44] or "piece"
        code, index = base, 2
        while ProductSchema.objects.filter(code=code).exists():
            code, index = f"{base}_{index}", index + 1
        return code

    @staticmethod
    @transaction.atomic
    def create(data):
        """One product per piece given : {instrument_model_id, pieces: [{component_id, name, price, image, model_3d, visible}]}."""
        model = InstrumentModel.objects.filter(pk=data.get("instrument_model_id")).first()
        if model is None:
            raise ValidationError("Modèle d'instrument introuvable.")
        pieces = data.get("pieces") or []
        if not pieces:
            raise ValidationError("Choisis au moins une pièce.")

        components = {
            c.pk: c
            for c in ProductComponent.objects.filter(
                pk__in=[p.get("component_id") for p in pieces],
                source_type="custom_piece",
                component_compatibilities__instrument_model=model,
            ).distinct()
        }
        existing = PieceProductBuilder._piece_products()
        product_type, _ = ProductType.objects.get_or_create(code=PRODUCT_TYPE)
        names = set()
        created = []
        for piece in pieces:
            component = components.get(piece.get("component_id"))
            if component is None:
                raise ValidationError("Cette pièce n'est pas configurable pour ce modèle d'instrument.")
            name = _text(piece.get("name"))
            if not name:
                raise ValidationError(f"Donne un nom au produit de la pièce {component.key}.")
            if (model.pk, component.pk) in existing:
                raise ValidationError(f"La pièce {component.key} est déjà vendue seule : {existing[(model.pk, component.pk)].name}.")
            if name.lower() in names or Product.objects.filter(name__iexact=name).exists():
                raise ValidationError(f"Un produit s'appelle déjà « {name} ».")
            names.add(name.lower())
            price = piece.get("price") or 0
            if price < 0:
                raise ValidationError("Le prix ne peut pas être négatif.")

            schema = ProductSchema.objects.create(name=name, code=PieceProductBuilder._schema_code(model, component))
            # the component is shared with the guitar : same part models, options and rules
            component.product_schemas.add(schema)
            product = Product.objects.create(
                name=name,
                price=price,
                product_type=product_type,
                product_schema=schema,
                instrument_model=model,
                image=_text(piece.get("image")),
                model_3d=_text(piece.get("model_3d")),
                is_visible=piece.get("visible", True),
            )
            created.append({"id": str(product.uuid), "name": product.name, "component": component.key})
        return created
