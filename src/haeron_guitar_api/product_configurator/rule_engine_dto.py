from dataclasses import dataclass
from typing import List, Dict


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
