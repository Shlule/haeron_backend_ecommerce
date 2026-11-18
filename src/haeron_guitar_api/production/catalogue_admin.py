"""Back-office "Catalogue" : the business data the configurator is built from, edited in one place.

- InstrumentType / InstrumentModel : guitar, bass... and the models of each (Starlight...) ;
- PartType / Series : kinds of pieces (body, neck...) and series ;
- Option : a question asked on a piece (color, material...) ;
- PartModel : a piece made in the workshop, with its values for each option (PartModelOption : the possible
  answers, with a price supplement, active or not) ;
- ComponentCompatibility : which part models are offered for an instrument model at a step of the configurator.

New part models are created by PartModelBuilder (it also creates their Vault key) ; this module edits them.
Codes that are written in serial numbers (part model, instrument type) cannot change once a part carries them.
A value used by a rule of the configurator is not deleted : it is deactivated instead.
"""

import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from ..models import (
    ComponentCompatibility,
    ConfigurationCondition,
    ConfigurationResult,
    ConfigurationRule,
    Instrument,
    InstrumentModel,
    InstrumentType,
    Option,
    Part,
    PartModel,
    PartModelOption,
    PartType,
    Product,
    ProductComponent,
    Series,
)

STATUSES = [value for value, _ in PartModel._meta.get_field("status").choices]


def _text(value):
    return (value or "").strip()


def _get(model, pk, label):
    instance = model.objects.filter(pk=pk).first() if pk else None
    if instance is None:
        raise ValidationError(f"{label} introuvable.")
    return instance


def _unique(model, field, value, instance, message):
    others = model.objects.filter(**{f"{field}__iexact": value})
    if instance is not None:
        others = others.exclude(pk=instance.pk)
    if others.exists():
        raise ValidationError(message)


def _ref(instance):
    return {"id": str(instance.pk), "name": instance.name} if instance else None


def _value_rules(value_ids):
    """{part model option id: names of the rules using it}, in a condition or a result."""
    used = {}
    for condition in ConfigurationCondition.objects.filter(
        compare_values__part_model_option_id__in=value_ids
    ).values("rule__name", "compare_values__part_model_option_id"):
        used.setdefault(condition["compare_values__part_model_option_id"], set()).add(condition["rule__name"])
    for result in ConfigurationResult.objects.filter(
        target_values__part_model_option_id__in=value_ids
    ).values("rule__name", "target_values__part_model_option_id"):
        used.setdefault(result["target_values__part_model_option_id"], set()).add(result["rule__name"])
    return {key: sorted(names) for key, names in used.items()}


def _steps_of(instrument_model):
    """Steps of the configurator where pieces of this instrument model are chosen (custom_piece components) :
    the ones already offering a part model for it, and the steps of the templates of its products."""
    return (
        ProductComponent.objects.filter(source_type="custom_piece")
        .filter(
            Q(component_compatibilities__instrument_model=instrument_model)
            | Q(product_schemas__schema_products__instrument_model=instrument_model)
        )
        .distinct()
        .order_by("key")
    )


def _step_products(component_ids):
    """{component id: [products whose template has this step]}."""
    products = {}
    for row in Product.objects.filter(product_schema__product_components__in=component_ids).values(
        "uuid", "name", "instrument_model_id", "product_schema__product_components"
    ).order_by("name"):
        products.setdefault(row["product_schema__product_components"], []).append(
            {"id": str(row["uuid"]), "name": row["name"], "instrumentModelId": str(row["instrument_model_id"] or "")}
        )
    return products


def _serialize_part_model(pm):
    return {
        "id": str(pm.uuid),
        "name": pm.name,
        "code": pm.code,
        "price": float(pm.price),
        "status": pm.status,
        "partType": _ref(pm.part_type),
        "series": _ref(pm.series),
    }


class CatalogueAdmin:
    # ---------------------------------------------------------------- reading

    @staticmethod
    def overview():
        part_models = list(
            PartModel.objects.select_related("part_type", "series")
            .annotate(value_count=Count("partmodeloption", distinct=True))
            .order_by("part_type__name", "name")
        )
        offered = {}
        for row in ComponentCompatibility.objects.filter(
            part_model__isnull=False, instrument_model__isnull=False
        ).values("part_model_id", "instrument_model__name").distinct():
            offered.setdefault(row["part_model_id"], set()).add(row["instrument_model__name"])

        option_usage = {
            row["option_id"]: row
            for row in PartModelOption.objects.values("option_id").annotate(
                values=Count("pk"), models=Count("part_model", distinct=True)
            )
        }
        return {
            "instrumentTypes": [
                {"id": str(t.uuid), "name": t.name, "code": t.code, "modelCount": t.model_count}
                for t in InstrumentType.objects.annotate(model_count=Count("instrument_models")).order_by("name")
            ],
            "instrumentModels": [
                {
                    "id": str(m.uuid),
                    "name": m.name,
                    "instrumentType": _ref(m.instrument_type),
                    "productCount": m.product_count,
                    "partModelCount": m.part_model_count,
                }
                for m in InstrumentModel.objects.select_related("instrument_type")
                .annotate(
                    product_count=Count("products", distinct=True),
                    part_model_count=Count(
                        "componentcompatibility__part_model", distinct=True
                    ),
                )
                .order_by("name")
            ],
            "partTypes": [
                {"id": str(t.uuid), "name": t.name, "code": t.code, "partModelCount": t.part_model_count}
                for t in PartType.objects.annotate(part_model_count=Count("partmodel")).order_by("name")
            ],
            "series": [
                {"id": str(s.uuid), "name": s.name, "code": s.code}
                for s in Series.objects.order_by("name")
            ],
            "options": [
                {
                    "id": str(o.uuid),
                    "name": o.name,
                    "category": o.category or "",
                    "description": o.description or "",
                    "valueCount": option_usage.get(o.uuid, {}).get("values", 0),
                    "partModelCount": option_usage.get(o.uuid, {}).get("models", 0),
                }
                for o in Option.objects.order_by("name")
            ],
            "partModels": [
                {
                    **_serialize_part_model(pm),
                    "valueCount": pm.value_count,
                    "instrumentModels": sorted(offered.get(pm.uuid, [])),
                }
                for pm in part_models
            ],
            "statuses": STATUSES,
        }

    @staticmethod
    def part_model(part_model_id):
        pm = PartModel.objects.select_related("part_type", "series").filter(pk=part_model_id).first()
        if pm is None:
            raise ValidationError("Pièce introuvable.")
        values = list(PartModelOption.objects.filter(part_model=pm).select_related("option").order_by("option__name", "name"))
        used = _value_rules([v.pk for v in values])
        groups = {}
        for value in values:
            group = groups.setdefault(value.option_id, {"id": str(value.option_id), "name": value.option.name, "values": []})
            group["values"].append(
                {
                    "id": str(value.uuid),
                    "name": value.name,
                    "code": value.code,
                    "priceDelta": float(value.price_delta),
                    "active": value.is_active,
                    "rules": used.get(value.pk, []),
                }
            )

        # values already used on other models, to add them again in one click
        known = {}
        for row in PartModelOption.objects.exclude(part_model=pm).order_by("name").values("option_id", "name", "code", "price_delta"):
            known.setdefault(str(row["option_id"]), {}).setdefault(
                row["code"], {"name": row["name"], "code": row["code"], "priceDelta": float(row["price_delta"])}
            )

        compatibilities = list(
            ComponentCompatibility.objects.filter(part_model=pm, instrument_model__isnull=False)
            .select_related("instrument_model", "component")
            .order_by("instrument_model__name", "component__key")
        )
        component_ids = {c.component_id for c in compatibilities}
        # every step of every instrument model, to offer the piece at a new one
        models = list(InstrumentModel.objects.order_by("name"))
        steps_by_model = {m.pk: list(_steps_of(m)) for m in models}
        for steps in steps_by_model.values():
            component_ids.update(s.pk for s in steps)
        products = _step_products(component_ids)

        def step(component, model_id):
            return {
                "id": str(component.uuid),
                "key": component.key,
                "products": [p["name"] for p in products.get(component.pk, []) if p["instrumentModelId"] == str(model_id)],
            }

        rules = ConfigurationRule.objects.filter(
            Q(target_part_model=pm)
            | Q(conditions__compare_values__part_model_option__part_model=pm)
            | Q(results__target_values__part_model_option__part_model=pm)
        ).distinct().order_by("name")

        return {
            "partModel": {
                **_serialize_part_model(pm),
                "partCount": Part.objects.filter(part_model=pm).count(),
                "discontinuedAt": pm.discontinued_at.isoformat() if pm.discontinued_at else None,
            },
            "options": list(groups.values()),
            "knownValues": {key: list(v.values()) for key, v in known.items()},
            "offeredIn": [
                {"instrumentModel": _ref(c.instrument_model), "step": step(c.component, c.instrument_model_id)}
                for c in compatibilities
            ],
            "steps": [
                {"instrumentModel": _ref(m), "steps": [step(s, m.pk) for s in steps_by_model[m.pk]]}
                for m in models
            ],
            "rules": [r.name for r in rules],
        }

    @staticmethod
    def instrument_model(instrument_model_id):
        model = InstrumentModel.objects.select_related("instrument_type").filter(pk=instrument_model_id).first()
        if model is None:
            raise ValidationError("Modèle d'instrument introuvable.")
        steps = list(_steps_of(model))
        products = _step_products([s.pk for s in steps])
        offered = {}
        for compat in (
            ComponentCompatibility.objects.filter(instrument_model=model, component__in=steps, part_model__isnull=False)
            .select_related("part_model__part_type", "part_model__series")
            .order_by("part_model__code")
        ):
            offered.setdefault(compat.component_id, []).append(_serialize_part_model(compat.part_model))
        return {
            "instrumentModel": {
                "id": str(model.uuid),
                "name": model.name,
                "instrumentType": _ref(model.instrument_type),
                "instrumentCount": Instrument.objects.filter(instrument_model=model).count(),
            },
            "steps": [
                {
                    "id": str(s.uuid),
                    "key": s.key,
                    "products": [
                        {"id": p["id"], "name": p["name"]}
                        for p in products.get(s.pk, [])
                        if p["instrumentModelId"] == str(model.pk)
                    ],
                    # other instrument models sharing the step : its part models are per model, not shared
                    "partModels": offered.get(s.pk, []),
                }
                for s in steps
            ],
            "products": [
                {"id": str(p.uuid), "name": p.name, "visible": p.is_visible}
                for p in Product.objects.filter(instrument_model=model).order_by("name")
            ],
        }

    # ---------------------------------------------------------------- instruments

    @staticmethod
    def save_instrument_type(data):
        instance = _get(InstrumentType, data["id"], "Type d'instrument") if data.get("id") else None
        name, code = _text(data.get("name")), _text(data.get("code")).upper()
        if not name:
            raise ValidationError("Donne un nom au type d'instrument.")
        if not re.fullmatch(r"[A-Z0-9]{2}", code):
            raise ValidationError("Le code d'un type d'instrument fait 2 lettres ou chiffres (il entre dans les numéros de série).")
        _unique(InstrumentType, "name", name, instance, f"Le type {name} existe déjà.")
        _unique(InstrumentType, "code", code, instance, f"Le code {code} est déjà pris.")
        if instance and instance.code != code and Part.objects.filter(serial_number__regex=rf"^.{{3}}{instance.code}-").exists():
            raise ValidationError(f"Des pièces portent déjà le code {instance.code} dans leur numéro de série : il ne peut plus changer.")
        instance = instance or InstrumentType()
        instance.name, instance.code = name, code
        instance.save()
        return {"id": str(instance.uuid), "name": instance.name, "code": instance.code}

    @staticmethod
    def save_instrument_model(data):
        instance = _get(InstrumentModel, data["id"], "Modèle d'instrument") if data.get("id") else None
        name = _text(data.get("name"))
        if not name:
            raise ValidationError("Donne un nom au modèle d'instrument.")
        _unique(InstrumentModel, "name", name, instance, f"Le modèle {name} existe déjà.")
        instrument_type = _get(InstrumentType, data.get("instrument_type_id"), "Type d'instrument")
        instance = instance or InstrumentModel()
        instance.name, instance.instrument_type = name, instrument_type
        instance.save()
        return {"id": str(instance.uuid), "name": instance.name, "instrumentType": _ref(instrument_type)}

    # ---------------------------------------------------------------- part types, series, options

    @staticmethod
    def save_part_type(data):
        instance = _get(PartType, data["id"], "Type de pièce") if data.get("id") else None
        name, code = _text(data.get("name")), _text(data.get("code")).upper()
        if not name:
            raise ValidationError("Donne un nom au type de pièce.")
        if not code or len(code) > 5:
            raise ValidationError("Le code fait de 1 à 5 caractères.")
        _unique(PartType, "name", name, instance, f"Le type {name} existe déjà.")
        _unique(PartType, "code", code, instance, f"Le code {code} est déjà pris.")
        instance = instance or PartType()
        instance.name, instance.code = name, code
        instance.save()
        return {"id": str(instance.uuid), "name": instance.name, "code": instance.code}

    @staticmethod
    def save_series(data):
        instance = _get(Series, data["id"], "Série") if data.get("id") else None
        name, code = _text(data.get("name")), _text(data.get("code")).upper()
        if not name:
            raise ValidationError("Donne un nom à la série.")
        if not code or len(code) > 5:
            raise ValidationError("Le code fait de 1 à 5 caractères.")
        _unique(Series, "name", name, instance, f"La série {name} existe déjà.")
        _unique(Series, "code", code, instance, f"Le code {code} est déjà pris.")
        instance = instance or Series()
        instance.name, instance.code = name, code
        instance.save()
        return {"id": str(instance.uuid), "name": instance.name, "code": instance.code}

    @staticmethod
    def save_option(data):
        instance = _get(Option, data["id"], "Option") if data.get("id") else None
        name = _text(data.get("name"))
        if not name:
            raise ValidationError("Donne un nom à l'option.")
        _unique(Option, "name", name, instance, f"L'option {name} existe déjà.")
        instance = instance or Option()
        instance.name = name[:100]
        instance.category = _text(data.get("category"))[:100] or None
        instance.description = _text(data.get("description")) or None
        instance.save()
        return {"id": str(instance.uuid), "name": instance.name, "category": instance.category or "", "description": instance.description or ""}

    @staticmethod
    def delete_option(option_id):
        option = _get(Option, option_id, "Option")
        count = PartModelOption.objects.filter(option=option).count()
        if count:
            raise ValidationError(f"{count} valeur(s) de pièces utilisent l'option {option.name} : retire-les d'abord.")
        if ConfigurationCondition.objects.filter(source_option=option).exists() or ConfigurationResult.objects.filter(target_option=option).exists():
            raise ValidationError(f"Des règles du configurateur utilisent l'option {option.name}.")
        option.delete()
        return True

    # ---------------------------------------------------------------- part models and their values

    @staticmethod
    def save_part_model(part_model_id, data):
        pm = _get(PartModel, part_model_id, "Pièce")
        name, code = _text(data.get("name")), _text(data.get("code")).upper()
        if not name:
            raise ValidationError("Donne un nom à la pièce.")
        if not code or len(code) > 5:
            raise ValidationError("Le code fait de 1 à 5 caractères.")
        if code != pm.code:
            _unique(PartModel, "code", code, pm, f"Le code {code} est déjà utilisé.")
            if Part.objects.filter(part_model=pm).exists():
                raise ValidationError(f"Des pièces {pm.code} sont déjà fabriquées : le code est dans leur numéro de série, il ne peut plus changer.")
        status = data.get("status") or pm.status
        if status not in STATUSES:
            raise ValidationError("Statut inconnu.")
        price = data.get("price")
        if price is None or price < 0:
            raise ValidationError("Le prix ne peut pas être négatif.")
        pm.name, pm.code, pm.price = name[:100], code, price
        pm.part_type = _get(PartType, data.get("part_type_id"), "Type de pièce")
        pm.series = _get(Series, data["series_id"], "Série") if data.get("series_id") else None
        if status != pm.status:
            pm.status = status
            # same as PartModelService.update : date at which the model stopped being sold
            pm.discontinued_at = (pm.discontinued_at or timezone.now()) if status in ("service_only", "discontinued") else None
        pm.save()
        return CatalogueAdmin.part_model(pm.pk)

    @staticmethod
    @transaction.atomic
    def save_value(part_model_id, data):
        """Create (no id) or change one possible value of an option on a part model."""
        pm = _get(PartModel, part_model_id, "Pièce")
        if data.get("id"):
            value = PartModelOption.objects.filter(pk=data["id"], part_model=pm).select_related("option").first()
            if value is None:
                raise ValidationError("Valeur introuvable sur cette pièce.")
            option = value.option
        else:
            value = None
            if data.get("option_id"):
                option = _get(Option, data["option_id"], "Option")
            else:
                new_name = _text(data.get("new_option_name"))
                if not new_name:
                    raise ValidationError("Choisis une option ou donne le nom d'une nouvelle option.")
                option = Option.objects.filter(name__iexact=new_name).first() or Option.objects.create(name=new_name[:100])
        code = _text(data.get("code"))
        name = _text(data.get("name")) or code
        if not code:
            raise ValidationError("Donne un code à la valeur.")
        same = PartModelOption.objects.filter(part_model=pm, option=option, code__iexact=code)
        if value is not None:
            same = same.exclude(pk=value.pk)
        if same.exists():
            raise ValidationError(f"{pm.name} a déjà la valeur {code} pour {option.name}.")
        value = value or PartModelOption(part_model=pm, option=option)
        value.code, value.name = code[:20], name[:100]
        value.price_delta = data.get("price_delta") or 0
        value.is_active = data.get("active", True)
        value.save()
        return CatalogueAdmin.part_model(pm.pk)

    @staticmethod
    def delete_value(value_id):
        value = PartModelOption.objects.filter(pk=value_id).first()
        if value is None:
            raise ValidationError("Valeur introuvable.")
        rules = _value_rules([value.pk]).get(value.pk)
        if rules:
            raise ValidationError(
                f"La valeur {value.code} est utilisée par les règles {', '.join(rules)} : désactive-la plutôt, elle ne sera plus proposée."
            )
        part_model_id = value.part_model_id
        value.delete()
        return CatalogueAdmin.part_model(part_model_id)

    # ---------------------------------------------------------------- where a part model is offered

    @staticmethod
    def link(part_model_id, instrument_model_id, component_id):
        """Offer the part model for this instrument model at this step of the configurator."""
        pm = _get(PartModel, part_model_id, "Pièce")
        model = _get(InstrumentModel, instrument_model_id, "Modèle d'instrument")
        component = ProductComponent.objects.filter(pk=component_id, source_type="custom_piece").first()
        if component is None:
            raise ValidationError("Cette étape ne propose pas de pièces fabriquées.")
        if not ComponentCompatibility.objects.filter(instrument_model=model, part_model=pm, component=component).exists():
            ComponentCompatibility.objects.create(instrument_model=model, part_model=pm, component=component)
        return True

    @staticmethod
    def unlink(part_model_id, instrument_model_id, component_id):
        ComponentCompatibility.objects.filter(
            instrument_model_id=instrument_model_id, part_model_id=part_model_id, component_id=component_id
        ).delete()
        return True
