from uuid import UUID
from django.forms import ValidationError
from ...models import PartModel, PartModelOption
from .base_handler import BaseProductHandler


class CustomPieceHandler(BaseProductHandler):
    CONFIG_SCHEMA = {
        "type": "object",
        "required": ["part_model_id"],
        "properties": {
            "part_model_id": {"type": "string"},
            "part_model_option_ids": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    }

    def _validate_business(self, config):
        part_model_id = config.get("part_model_id")
        part_model_option_ids = config.get("part_model_option_ids")

        part_model = (
            PartModel.objects.select_related("part_type")
            .prefetch_related("part_type__instrument_types")
            .get(pk=part_model_id)
        )
        part_model_options = PartModelOption.objects.filter(pk__in=part_model_option_ids, part_model=part_model)
        if part_model_options.count() != len(part_model_option_ids):
            raise ValidationError("invalid Options")

        return {"part_model": part_model, "options": part_model_options}

    def build_snapshot(self, data):

        part_model = data["part_model"]
        options = data["options"]

        return {
            "part_model": {
                "id": str(part_model.uuid),
                "name": part_model.name,
            },
            "part_type": {
                "name": part_model.part_type.name,
            },
            "instrument_type": {
                "name": part_model.part_type.instrument_types.name,
            },
            "options": [
                {
                    "name": option.option.name,
                    "value": option.name,
                    "price_delta": float(option.price_delta),
                }
                for option in options
            ],
        }

    def calculate_price(self, data):

        total = data["part_model"].price

        for option in data["options"]:
            total += option.price_delta

        return total
