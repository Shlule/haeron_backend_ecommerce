from dataclasses import dataclass
from typing import List, Dict
from ..models import ConfigurationRule, ConfigurationCondition, ConfigurationResult


# @dataclass
# class ConditionDTO:
#     field: str
#     operator: str
#     value: str


# @dataclass
# class EffectDTO:
#     field: str
#     type: str
#     values: List[str]


# @dataclass
# class RuleDTO:
#     rule_name: str
#     conditions: List[ConditionDTO]
#     effects: List[EffectDTO]


# @dataclass
# class ConfigDTO:
#     fields: Dict[str, List[str]]
#     rules: List[RuleDTO]


@dataclass
class ProductConfigurationDTO:
    product_id: str
    components: list["ComponentDTO"]
    rules: list["RuleDTO"]


@dataclass
class ComponentDTO:
    key: str
    type: str
    part_model_id: "PartModelDTO"
    part_model_options_ids: list["PartModelOptionDTO"]


@dataclass
class PartModelDTO:
    id: str
    name: str
    price: float


@dataclass
class PartModelOptionDTO:
    id: str
    name: str
    code: str
    options: list["OptionDTO"]
    price_delta: float


@dataclass
class OptionDTO:
    id: str

    label: str

    values: list["ValueDTO"]


@dataclass
class ValueDTO:
    id: str
    label: str

    price_delta: float


@dataclass
class RuleDTO:
    id: str
    name: str
    conditions: list["ConditionDTO"]

    results: list["ResultDTO"]


def toRuleDto(list_ruleModel: List[ConfigurationRule]):
    result = []
    for rule_model in list_ruleModel:
        conditions = [toConditionDto(condition) for condition in rule_model.conditions.all()]
        results = [toResultDto(result) for result in rule_model.results.all()]
        rule = RuleDTO(id=rule_model.uuid, name=rule_model.name, conditions=conditions, results=results)
        result.append(rule)
    return result


def toConditionDto(conditionModel: List[ConfigurationCondition]):

    return ConditionDTO(
        component=conditionModel.source_component,
        option=conditionModel.source_option,
        values=conditionModel.compare_values,
        operator=conditionModel.operator,
    )


def toResultDto(resultModel: List[ConfigurationResult]):
    return ResultDTO(
        component=resultModel.target_component,
        option=resultModel.target_option,
        target_values=resultModel.target_values,
    )


@dataclass
class ConditionDTO:
    component: str
    option: str
    values: list[str]

    operator: str


@dataclass
class ResultDTO:
    component: str
    option: str
    # action: str

    target_values: list[str]


@dataclass
class ProductSelectionDTO:
    product_id: str

    selections: dict[str, str]
