from dataclasses import asdict
from pprint import pprint
from ..models import (
    ConfigurationCondition,
    ComponentCompatibility,
    ConfigurationResult,
    Product,
    ConfigurationRule,
    PartModel,
    ProductComponent,
    PartModelOption,
)

from .rule_engine_dto import RuleDTO, ConditionDTO, ValueDTO, ResultDTO
from django.db import models
import logging

log = logging.getLogger(__name__)


class RuleEngine:
    def _apply(self, rule, configuration):
        for result in rule.results.all():
            component = next(c for c in configuration.components if c.key == result.target_component.key)

            component.allowed_values = result.allowed_values
            component.disabled = False

    def collect_rules(self, product: Product):

        part_models = PartModel.objects.filter(
            componentcompatibility__component__product_schemas=product.product_schema
        ).distinct()

        rules = ConfigurationRule.objects.filter(
            models.Q(target_schema=product.product_schema)
            | models.Q(target_component__product_schemas=product.product_schema)
            | models.Q(target_part_model__in=part_models)
        ).prefetch_related(
            "conditions",
            "results",
            "conditions__source_component",
            "results__target_component",
        )

        compatibilities = ComponentCompatibility.objects.filter(
            component__product_schemas=product.product_schema, instrument_model=product.instrument_model
        ).select_related("part_model", "component")

        part_model_options = PartModelOption.objects.filter(
            part_model__componentcompatibility__component__product_schemas=product.product_schema
        ).select_related("option", "part_model")
        return {
            "rules": list(rules),
            "compatibilities": list(compatibilities),
            "part_model_options": list(part_model_options),
        }

    def serialize_rule(self, rule: ConfigurationRule):
        return RuleDTO(
            id=rule.uuid,
            name=rule.name,
            conditions=[self.serialize_condition(c) for c in rule.conditions.all()],
            results=[self.serialize_result(r) for r in rule.results.all()],
        )

    # {
    #     "id": str(rule.uuid),
    #     "name": rule.name,
    #     # "scope": self._get_rule_scope(rule),
    #     "conditions": [self.serialize_condition(c) for c in rule.conditions.all()],
    #     "results": [self.serialize_result(r) for r in rule.results.all()],
    # }

    def serialize_condition(self, condition: ConfigurationCondition):

        return ConditionDTO(
            component=condition.source_component,
            operator=condition.operator,
            values=[self.serialize_value(v) for v in condition.compare_values.all()],
            option=condition.source_option,
        )

        # return {
        #     "source": condition.source_component.key,
        #     "operator": condition.operator,
        #     "values": [self.serialize_value(v) for v in condition.values],
        # }

    def serialize_result(self, result: ConfigurationResult):

        return ResultDTO(
            component=result.target_component,
            option=result.target_option,
            target_values=[self.serialize_value(v) for v in result.target_values.all()],
        )

        # return {
        #     "target": result.target_component.key,
        #     "values": [self.serialize_value(v) for v in result.values],
        # }

    def serialize_value(self, value):

        if value.part_model_option:
            return {
                "type": "option",
                "id": str(value.part_model_option.uuid),
                "code": value.part_model_option.code,
                "label": value.part_model_option.name,
            }

        if value.product_component_choice:
            product = value.product_component_choice.product
            return {
                "type": "product",
                "id": str(product.uuid),
                "label": product.name,
            }

        return None

    def serialize_snapshot(self, snapshot):
        return {"rules": [self.serialize_rule(rule) for rule in snapshot["rules"]]}

    def check(self, configuration: dict, rules: list[RuleDTO]):
        violations = []

        for rule in rules:
            if not self._rule_applies(rule, configuration):
                continue

            violations += self._check_rule(rule, configuration)

        return violations

    @staticmethod
    def value_key(component, option=None):
        # key used in the normalized configuration : "<component_key>.<option_name>"
        # if the option is empty the value is the product selected for the component (product_choice)
        component_key = component.key if hasattr(component, "key") else component
        option_name = option.name if hasattr(option, "name") else option
        return f"{component_key}.{option_name}" if option_name else component_key

    def _rule_applies(self, rule: RuleDTO, config: dict) -> bool:

        for condition in rule.conditions:
            value = config.get(self.value_key(condition.component, condition.option))

            if value is None:
                return False

            compare_values = {v["id"] for v in condition.values if v}
            operator = getattr(condition, "operator", "eq") or "eq"

            if operator == "neq":
                if str(value) in compare_values:
                    return False
            elif str(value) not in compare_values:
                # "eq" and "in" share the same behaviour : the value must be in the list
                return False

        return True

    def _check_rule(self, rule: RuleDTO, config: dict):
        violations = []

        for result in rule.results:
            key = self.value_key(result.component, result.option)

            selected_value = config.get(key)

            allowed = {v["id"] for v in result.target_values if v}

            if selected_value and str(selected_value) not in allowed:
                violations.append(
                    {
                        "rule_id": str(rule.id),
                        "rule_name": rule.name,
                        "component": key,
                        "message": "invalid configuration according to rule",
                    }
                )

        return violations

    # plain JSON version of the rules for the front end (so the front can apply them in autonomy)
    def serialize_rule_json(self, rule: ConfigurationRule):
        return {
            "id": str(rule.uuid),
            "name": rule.name,
            "conditions": [
                {
                    "component": c.source_component.key,
                    "option": c.source_option.name,
                    "operator": c.operator,
                    "values": [v for v in (self.serialize_value(v) for v in c.compare_values.all()) if v],
                }
                for c in rule.conditions.all()
            ],
            "results": [
                {
                    "component": r.target_component.key,
                    "option": r.target_option.name,
                    "values": [v for v in (self.serialize_value(v) for v in r.target_values.all()) if v],
                }
                for r in rule.results.all()
            ],
        }
