from calendar import c
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
    # def __init__(self, rules):
    #     self.rules = rules

    # def apply(self, configuration, context):

    #     for rule in self.rules:
    #         if self._match(rule, context):
    #             self._apply(rule, configuration)

    #     return configuration

    # def _match(self, rule, context):
    #     for condition in rule.conditions.all():
    #         value = context.get(condition.source_component.key)

    #         if condition.operator == "eq":
    #             if value not in condition.values:
    #                 return False

    #         if condition.operator == "in":
    #             if value not in condition.values:
    #                 return False

    #     return True

    def _apply(self, rule, configuration):
        for result in rule.results.all():
            component = next(c for c in configuration.components if c.key == result.target_component.key)

            component.allowed_values = result.allowed_values
            component.disabled = False

    def collect_rules(self, product: Product):

        rules = ConfigurationRule.objects.filter(
            models.Q(target_schema=product.product_schema)
            | models.Q(target_component__product_schemas=product.product_schema)
            | models.Q(target_part_model__isnull=False)
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
        # pprint("[]" * 50)
        # pprint(condition.values)

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

        if value.product:
            return {
                "type": "product",
                "id": str(value.product.uuid),
                "label": value.product.name,
            }

        return None

    def serialize_snapshot(self, snapshot):
        return {"rules": [self.serialize_rule(rule) for rule in snapshot["rules"]]}
