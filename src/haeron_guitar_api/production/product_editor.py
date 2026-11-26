"""Back-office editor of a shop product and its template (the configuration the customer can choose).

Same tables as before, read by the configurator, the cart and the rule engine without any change :
- Product : name, base price, instrument model, pictures, visible in the shop ;
- ProductSchema : the template of a configurable product, made of components ;
- ProductComponent : one step of the configurator, with its key (body_sup, neck...) and its kind :
    custom_piece  -> a piece made in the workshop : the part models offered (ComponentCompatibility for the instrument
                     model of the product), each with its option values (PartModelOption, edited in "Pièces et prix") ;
    product_choice -> one product to pick in a list (ProductComponentChoice), e.g. pickups ;
    fixed         -> one product always included.
A component can belong to several schemas (a piece sold alone shares the component of its guitar) :
changing its part models changes them everywhere it is used, removing it from a template only unlinks it.
"""

import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils.text import slugify

from ..models import (
    ComponentCompatibility,
    ConfigurationRule,
    InstrumentModel,
    PartModel,
    PartModelOption,
    Product,
    ProductComponent,
    ProductComponentChoice,
    ProductSchema,
    ProductType,
)
from .product_catalogue import ProductCatalogue, _text

CONFIGURABLE_TYPE = "bundle_dynamique"
SOURCE_TYPES = ["custom_piece", "product_choice", "fixed"]
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,49}$")


def _product(product_id):
    product = Product.objects.select_related("product_type", "product_schema", "instrument_model").filter(pk=product_id).first()
    if product is None:
        raise ValidationError("Produit introuvable.")
    return product


def _component_of(product, component_id):
    if not product.product_schema_id:
        raise ValidationError("Ce produit n'a pas de template.")
    component = product.product_schema.product_components.filter(pk=component_id).first()
    if component is None:
        raise ValidationError("Cette étape ne fait pas partie du template de ce produit.")
    return component


class ProductEditor:
    # ---------------------------------------------------------------- reading

    @staticmethod
    def catalog():
        """What a template can use : instrument models, part models with their option values, products to pick."""
        values = {}
        for value in PartModelOption.objects.select_related("option").order_by("option__name", "name"):
            groups = values.setdefault(value.part_model_id, {})
            groups.setdefault(value.option.name, []).append(
                {"name": value.name, "code": value.code, "priceDelta": float(value.price_delta), "active": value.is_active}
            )
        part_models = PartModel.objects.select_related("part_type").order_by("part_type__name", "name")
        return {
            "instrumentModels": [
                {"id": str(m.uuid), "name": m.name} for m in InstrumentModel.objects.order_by("name")
            ],
            "partModels": [
                {
                    "id": str(pm.uuid),
                    "name": pm.name,
                    "code": pm.code,
                    "partType": pm.part_type.name,
                    "price": float(pm.price),
                    "status": pm.status,
                    "options": [{"option": name, "values": vals} for name, vals in values.get(pm.uuid, {}).items()],
                }
                for pm in part_models
            ],
            # products sold as they are, to be picked in a product_choice step or included in a fixed one
            "products": [
                {"id": str(p.uuid), "name": p.name, "price": float(p.price)}
                for p in Product.objects.filter(product_schema__isnull=True).order_by("name")
            ],
            "sourceTypes": SOURCE_TYPES,
        }

    @staticmethod
    def editor(product_id):
        product = ProductCatalogue._products().get(pk=_product(product_id).pk)
        data = {"product": {**ProductCatalogue.serialize(product), "instrumentModelId": str(product.instrument_model_id) if product.instrument_model_id else None}}
        if not product.product_schema_id:
            data["components"] = []
            data["templateRules"] = []
            return data

        schema = product.product_schema
        components = list(
            schema.product_components.annotate(schema_count=Count("product_schemas")).order_by("key")
        )
        component_ids = [c.pk for c in components]

        part_models = {}
        for compat in ComponentCompatibility.objects.filter(
            component_id__in=component_ids, instrument_model_id=product.instrument_model_id, part_model__isnull=False
        ).order_by("part_model__code"):
            part_models.setdefault(compat.component_id, []).append(compat.part_model_id)

        choices = {}
        for choice in ProductComponentChoice.objects.filter(component_id__in=component_ids):
            choices.setdefault(choice.component_id, []).append(str(choice.product_id))

        # other products using the same steps (a piece sold alone, another guitar)
        shared = {}
        for other in Product.objects.filter(product_schema__product_components__in=component_ids).exclude(pk=product.pk).values(
            "uuid", "name", "product_schema__product_components"
        ):
            shared.setdefault(other["product_schema__product_components"], []).append({"id": str(other["uuid"]), "name": other["name"]})

        all_part_models = {pm for ids in part_models.values() for pm in ids}
        rules = list(
            ConfigurationRule.objects.filter(
                Q(target_schema=schema) | Q(target_component_id__in=component_ids) | Q(target_part_model_id__in=all_part_models)
            )
            .distinct()
            .order_by("name")
        )

        def rules_of(component):
            mine = set(part_models.get(component.pk, []))
            return [
                {"id": str(r.uuid), "name": r.name}
                for r in rules
                if r.target_component_id == component.pk or r.target_part_model_id in mine
            ]

        data["components"] = [
            {
                "id": str(c.uuid),
                "key": c.key,
                "sourceType": c.source_type,
                "partModelIds": [str(pm) for pm in part_models.get(c.pk, [])],
                "choiceProductIds": choices.get(c.pk, []),
                "fixedProductId": str(c.fixed_product_id) if c.fixed_product_id else None,
                "sharedWith": shared.get(c.pk, []),
                "rules": rules_of(c),
            }
            for c in components
        ]
        data["templateRules"] = [{"id": str(r.uuid), "name": r.name} for r in rules if r.target_schema_id == schema.pk]
        return data

    # ---------------------------------------------------------------- product

    @staticmethod
    def _schema_code(name):
        base = slugify(name).replace("-", "_")[:44] or "produit"
        code, index = base, 2
        while ProductSchema.objects.filter(code=code).exists():
            code, index = f"{base}_{index}", index + 1
        return code

    @staticmethod
    def _instrument_model(model_id):
        if not model_id:
            return None
        model = InstrumentModel.objects.filter(pk=model_id).first()
        if model is None:
            raise ValidationError("Modèle d'instrument introuvable.")
        return model

    @staticmethod
    def _check_name(name, exclude=None):
        if not name:
            raise ValidationError("Donne un nom au produit.")
        if Product.objects.filter(name__iexact=name).exclude(pk=exclude).exists():
            raise ValidationError(f"Un produit s'appelle déjà « {name} ».")

    @staticmethod
    @transaction.atomic
    def create_configurable(data):
        """A new product to configure, with an empty template. Hidden by default : shown once its template is ready."""
        name = _text(data.get("name"))
        ProductEditor._check_name(name)
        model = ProductEditor._instrument_model(data.get("instrument_model_id"))
        if model is None:
            raise ValidationError("Choisis le modèle d'instrument : il donne les pièces compatibles.")
        product_type, _ = ProductType.objects.get_or_create(code=CONFIGURABLE_TYPE)
        schema = ProductSchema.objects.create(name=name, code=ProductEditor._schema_code(name))
        product = Product.objects.create(
            name=name,
            price=ProductCatalogue._price(data.get("price")),
            product_type=product_type,
            product_schema=schema,
            instrument_model=model,
            image=_text(data.get("image")),
            model_3d=_text(data.get("model_3d")),
            is_visible=bool(data.get("visible", False)),
        )
        return ProductEditor.editor(product.pk)

    @staticmethod
    @transaction.atomic
    def update_product(product_id, data):
        product = _product(product_id)
        name = _text(data.get("name"))
        ProductEditor._check_name(name, exclude=product.pk)
        model = ProductEditor._instrument_model(data.get("instrument_model_id"))
        if product.product_schema_id and (model.pk if model else None) != product.instrument_model_id:
            # the part models of the steps are chosen for one instrument model
            used = ComponentCompatibility.objects.filter(
                component__product_schemas=product.product_schema, instrument_model_id=product.instrument_model_id
            ).exists()
            if used:
                raise ValidationError("Retire d'abord les modèles de pièce des étapes pour changer le modèle d'instrument.")
            if model is None:
                raise ValidationError("Un produit à configurer a besoin d'un modèle d'instrument.")
        product.name = name
        product.price = ProductCatalogue._price(data.get("price"))
        product.instrument_model = model
        product.image = _text(data.get("image"))
        product.model_3d = _text(data.get("model_3d"))
        product.is_visible = bool(data.get("visible", product.is_visible))
        product.save()
        if product.product_schema_id:
            ProductSchema.objects.filter(pk=product.product_schema_id).update(name=name)
        return ProductEditor.editor(product.pk)

    # ---------------------------------------------------------------- template

    @staticmethod
    def _check_key(product, key, exclude=None):
        if not KEY_PATTERN.match(key):
            raise ValidationError("Le code de l'étape : lettres minuscules, chiffres et _ (ex : body_sup).")
        if product.product_schema.product_components.filter(key=key).exclude(pk=exclude).exists():
            raise ValidationError(f"Le template a déjà une étape « {key} ».")

    @staticmethod
    @transaction.atomic
    def add_component(product_id, key, source_type, fixed_product_id=None):
        product = _product(product_id)
        if not product.product_schema_id:
            raise ValidationError("Ce produit se vend tel quel : il n'a pas de template.")
        key = _text(key)
        ProductEditor._check_key(product, key)
        if source_type not in SOURCE_TYPES:
            raise ValidationError("Type d'étape inconnu.")
        fixed = None
        if source_type == "fixed":
            # the configurator cannot show a fixed step without its product
            fixed = Product.objects.filter(pk=fixed_product_id).first() if fixed_product_id else None
            if fixed is None:
                raise ValidationError("Choisis le produit toujours inclus.")
        component = ProductComponent.objects.create(key=key, source_type=source_type, fixed_product=fixed)
        component.product_schemas.add(product.product_schema)
        return ProductEditor.editor(product.pk)

    @staticmethod
    @transaction.atomic
    def update_component(product_id, component_id, data):
        product = _product(product_id)
        component = _component_of(product, component_id)

        key = _text(data.get("key")) or component.key
        if key != component.key:
            ProductEditor._check_key(product, key, exclude=component.pk)
            component.key = key

        if component.source_type == "custom_piece":
            if not product.instrument_model_id:
                raise ValidationError("Choisis d'abord le modèle d'instrument du produit.")
            wanted = {str(i) for i in data.get("part_model_ids") or []}
            found = {str(pk) for pk in PartModel.objects.filter(pk__in=wanted).values_list("pk", flat=True)}
            if found != wanted:
                raise ValidationError("Modèle de pièce introuvable.")
            current = ComponentCompatibility.objects.filter(component=component, instrument_model_id=product.instrument_model_id)
            current.exclude(part_model_id__in=wanted).delete()
            have = {str(pk) for pk in current.values_list("part_model_id", flat=True)}
            ComponentCompatibility.objects.bulk_create(
                [
                    ComponentCompatibility(component=component, instrument_model_id=product.instrument_model_id, part_model_id=pm)
                    for pm in sorted(wanted - have)
                ]
            )

        elif component.source_type == "product_choice":
            wanted = {str(i) for i in data.get("choice_product_ids") or []}
            if len(wanted) != Product.objects.filter(pk__in=wanted).count():
                raise ValidationError("Produit introuvable.")
            ProductComponentChoice.objects.filter(component=component).exclude(product_id__in=wanted).delete()
            have = {str(pk) for pk in ProductComponentChoice.objects.filter(component=component).values_list("product_id", flat=True)}
            ProductComponentChoice.objects.bulk_create(
                [ProductComponentChoice(component=component, product_id=pid) for pid in sorted(wanted - have)]
            )

        elif component.source_type == "fixed":
            fixed_id = data.get("fixed_product_id")
            if not fixed_id or not Product.objects.filter(pk=fixed_id).exists():
                raise ValidationError("Choisis le produit toujours inclus.")
            component.fixed_product_id = fixed_id

        component.save()
        return ProductEditor.editor(product.pk)

    @staticmethod
    @transaction.atomic
    def remove_component(product_id, component_id):
        """Takes the step out of this template. A step used nowhere else is deleted, with its rules."""
        product = _product(product_id)
        component = _component_of(product, component_id)
        component.product_schemas.remove(product.product_schema)
        if not component.product_schemas.exists():
            component.delete()
        return ProductEditor.editor(product.pk)
