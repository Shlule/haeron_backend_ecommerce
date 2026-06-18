from collections import Counter
from decimal import Decimal
from pprint import pprint
from django.forms import ValidationError
from ....models import PartModel, PartModelOption, ComponentCompatibility
from ..handlers.base_component_handler import BaseComponentHandler
from ..product_component_registry import ComponentHandlerRegistry
from ....types.product_configurator_types import CustomPieceComponent


@ComponentHandlerRegistry.register("custom_piece")
class CustomPieceHandler(BaseComponentHandler):
    CONFIG_SCHEMA = {
        "type": "object",
        "required": ["part_model_id"],
        "properties": {
            "part_model_id": {"type": "string"},
            "part_model_option_ids": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    }

    def _validate_business(self, component, config, product):
        part_model_id = config.get("part_model_id", "")
        part_model_option_ids = config.get("part_model_option_ids", [])

        part_model = PartModel.objects.get(pk=part_model_id)
        part_model_options = PartModelOption.objects.select_related("option").filter(
            pk__in=part_model_option_ids, part_model=part_model
        )

        options = [part_model_option.option.name for part_model_option in part_model_options]
        options_count = Counter(options)
        option_duplicates = [option for option, count in options_count.items() if count > 1]
        if option_duplicates:
            raise ValidationError(f"to much value selected for option {option_duplicates}")

        if part_model_options.count() != len(part_model_option_ids):
            raise ValidationError("invalid Options")

        return {"part_model": part_model, "part_models_options": part_model_options}

    def _resolve(self, component, config, product=None, **kwargs):

        if not config or "part_model_id" not in config:
            raise ValidationError(f"{component} requires part_model_id")

        part_model = PartModel.objects.select_related("part_type").get(pk=config["part_model_id"])

        part_model_options_ids = config.get("part_model_option_ids", [])
        selected_part_model_options = PartModelOption.objects.filter(
            part_model=part_model, pk__in=part_model_options_ids
        )

        if len(part_model_options_ids) != selected_part_model_options.count():
            raise ValidationError("Invalid options")

        base_price = part_model.price
        options_price = sum(option.price_delta for option in selected_part_model_options)
        if product.instrument_model:
            is_valid = ComponentCompatibility.objects.filter(
                instrument_model=product.instrument_model, component=component, part_model=part_model
            )
            if not is_valid:
                raise ValidationError(f"{part_model.code}, not compatible with {component}")

        return {
            "type": "custom_piece",
            "component": component.key,
            "part_model_id": str(part_model.uuid),
            "options": [
                {
                    "id": str(part_model_option.uuid),
                    "name": part_model_option.option.name,
                    "value": part_model_option.name,
                }
                for part_model_option in selected_part_model_options
            ],
            "price": str(base_price + options_price),
        }

    def bulk_build_configuration(self, components, product):

        compatibilities = ComponentCompatibility.objects.filter(
            component__in=components,
            instrument_model=product.instrument_model,
        ).select_related("part_model", "component")

        part_model_ids = compatibilities.values_list("part_model_id", flat=True)

        options = PartModelOption.objects.filter(part_model_id__in=part_model_ids).select_related("option")

        # group options by part_model_id
        options_by_part_model = {}
        for opt in options:
            options_by_part_model.setdefault(opt.part_model_id, []).append(opt)

        # group compatibilities by component_id
        compat_by_component = {}
        for c in compatibilities:
            compat_by_component.setdefault(c.component_id, []).append(c)

        result = []

        for comp in components:
            part_models_data = []

            for compat in compat_by_component.get(comp.uuid, []):
                pm = compat.part_model

                part_models_data.append(
                    {
                        "id": str(pm.uuid),
                        "name": pm.name,
                        "price": float(pm.price),
                        "options": [
                            {
                                "id": str(opt.uuid),
                                "name": opt.option.name,
                                "value": opt.name,
                                "price_delta": float(opt.price_delta),
                            }
                            for opt in options_by_part_model.get(pm.uuid, [])
                        ],
                    }
                )

            result.append(
                {
                    "key": comp.key,
                    "type": "custom_piece",
                    "part_models": part_models_data,
                }
            )

        return result

    def build_configuration_component(self, component, product):
        part_models = PartModel.objects.filter(
            componentcompatibility__component=component,
            componentcompatibility__instrument_model=product.instrument_model,
        ).prefetch_related("partmodeloption_set")

        return CustomPieceComponent(key=component.key, part_models=part_models)


# JSON attendu cotes Front
# {
#   "component": "neck",
#   "configuration": {
#     "part_model_id": "uuid-du-part-model",
#     "part_model_option_ids": [
#       "uuid-part_model_option-1",
#       "uuid-part_model_option-2"
#     ]
#   }
# }
