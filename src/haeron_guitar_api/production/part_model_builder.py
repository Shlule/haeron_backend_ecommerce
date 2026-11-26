"""New part model of the catalogue in one step : the model, its options and their values (PartModelOption).

Used by the back-office "Nouvelle pièce" form of the catalogue. Everything is created in one transaction ;
the Vault domain key of the model is created last, so a Vault error leaves nothing half made.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import Option, PartModel, PartModelOption, PartType, Series
from ..security.vault.vault_factory import get_vault_service

STATUSES = [value for value, _ in PartModel._meta.get_field("status").choices]


def _text(value):
    return (value or "").strip()


class PartModelBuilder:
    @staticmethod
    def form_data():
        """Part types, series, and every option with the values already used on other models (to pick them again)."""
        known = {}
        for value in PartModelOption.objects.order_by("name").values("option_id", "name", "code", "price_delta"):
            values = known.setdefault(value["option_id"], {})
            values.setdefault(value["code"], {"name": value["name"], "code": value["code"], "priceDelta": float(value["price_delta"])})
        return {
            "partTypes": [{"id": str(t.uuid), "name": t.name, "code": t.code} for t in PartType.objects.order_by("name")],
            "series": [{"id": str(s.uuid), "name": s.name, "code": s.code} for s in Series.objects.order_by("name")],
            "statuses": STATUSES,
            "options": [
                {"id": str(o.uuid), "name": o.name, "category": o.category, "knownValues": list(known.get(o.uuid, {}).values())}
                for o in Option.objects.order_by("name")
            ],
        }

    @staticmethod
    @transaction.atomic
    def create(data):
        name, code = _text(data.get("name")), _text(data.get("code")).upper()
        if not name:
            raise ValidationError("Donne un nom à la pièce.")
        if not code or len(code) > 5:
            raise ValidationError("Le code fait de 1 à 5 caractères.")
        if PartModel.objects.filter(code__iexact=code).exists():
            raise ValidationError(f"Le code {code} est déjà utilisé.")
        part_type = PartType.objects.filter(pk=data.get("part_type_id")).first()
        if part_type is None:
            raise ValidationError("Choisis le type de pièce.")
        series = None
        if data.get("series_id"):
            series = Series.objects.filter(pk=data["series_id"]).first()
            if series is None:
                raise ValidationError("Série introuvable.")
        status = data.get("status") or "active"
        if status not in STATUSES:
            raise ValidationError("Statut inconnu.")
        price = data.get("price") or 0
        if price < 0:
            raise ValidationError("Le prix ne peut pas être négatif.")

        part_model = PartModel.objects.create(name=name, code=code, part_type=part_type, series=series, price=price, status=status)

        values, seen_options = [], set()
        for group in data.get("options") or []:
            option = PartModelBuilder._option(group)
            if option.uuid in seen_options:
                raise ValidationError(f"L'option {option.name} est ajoutée deux fois.")
            seen_options.add(option.uuid)
            codes = set()
            for value in group.get("values") or []:
                value_code = _text(value.get("code"))
                value_name = _text(value.get("name")) or value_code
                if not value_code:
                    raise ValidationError(f"{option.name} : chaque valeur a besoin d'un code.")
                if value_code in codes:
                    raise ValidationError(f"{option.name} : la valeur {value_code} est ajoutée deux fois.")
                codes.add(value_code)
                values.append(
                    PartModelOption(
                        part_model=part_model,
                        option=option,
                        name=value_name[:100],
                        code=value_code[:20],
                        price_delta=value.get("price_delta") or 0,
                    )
                )
            if not codes:
                raise ValidationError(f"Ajoute au moins une valeur à l'option {option.name}.")
        PartModelOption.objects.bulk_create(values)

        # same as PartModelService.create : every part model has its own domain key in Vault
        get_vault_service().post_secret("domain", part_model_id=str(part_model.uuid))
        return {"id": str(part_model.uuid), "name": part_model.name, "code": part_model.code, "valueCount": len(values)}

    @staticmethod
    def _option(group):
        if group.get("option_id"):
            option = Option.objects.filter(pk=group["option_id"]).first()
            if option is None:
                raise ValidationError("Une des options n'existe plus.")
            return option
        name = _text(group.get("new_option_name"))
        if not name:
            raise ValidationError("Choisis une option ou donne le nom d'une nouvelle option.")
        # an option typed again by name is the existing one
        return Option.objects.filter(name__iexact=name).first() or Option.objects.create(name=name)
