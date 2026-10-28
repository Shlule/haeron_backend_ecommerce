import strawberry

from typing import Annotated, Union, List

from .types import ProductGQLType, OptionGQLType


@strawberry.type
class ProductConfiguration:
    product: strawberry.ID
    components: list["Component"]


Component = Annotated[
    Union[
        "CustomPieceComponent",
        "ProductChoiceComponent",
        "FixedComponent",
        "ProductConfigurableComponent",
    ],
    strawberry.union("Component"),
]


# @strawberry.type
# class OptionValueType:
#     id: str
#     name: str
#     code: str
#     price_delta: float


# @strawberry.type
# class OptionType:
#     name: str
#     values: list[OptionValueType]


@strawberry.type
class PartModelType:
    id: str
    name: str
    price: float
    options: list["OptionGQLType"]


@strawberry.type
class CustomPieceComponent:
    key: str
    type: str = "custom_piece"
    part_models: list[PartModelType]


@strawberry.type
class ProductChoiceComponent:
    key: str
    choices: list["ProductGQLType"]
    selected_product_id: str | None


@strawberry.type
class FixedComponent:
    key: str

    product_id: str
    name: str
    price: float


@strawberry.type
class ProductConfigurableComponent:
    key: str

    product_id: str
    name: str

    price: float
    snapshot: strawberry.scalars.JSON

    components: list["Component"]


@strawberry.type
class ProductConfigSchema:
    components: list["Component"]


@strawberry.type
class CustomPieceResult:
    type: str
    component: str
    part_model_id: str
    options: List["SelectedOption"]
    price: float


@strawberry.type
class SelectedOption:
    id: str
    name: str
    value: str


@strawberry.type
class ProductChoiceResult:
    type: str
    component: str
    product_id: str
    name: str
    price: float


@strawberry.type
class FixedResult:
    type: str
    component: str
    product_id: str
    name: str
    price: float


@strawberry.type
class ProductConfigurableResult:
    type: str
    component: str
    product_id: str
    snapshot: strawberry.scalars.JSON
    price: float


ComponentResult = Union[
    CustomPieceResult,
    ProductChoiceResult,
    FixedResult,
    ProductConfigurableResult,
]


@strawberry.type
class ProductConfigurationResult:
    product_id: str
    components: List[ComponentResult]
    total_price: float


@strawberry.input
class CustomPieceInput:
    part_model_id: str
    part_model_option_ids: List[str]


@strawberry.input
class ProductChoiceInput:
    product_id: str


@strawberry.input
class ProductConfigurableInput:
    product_id: str
    configuration: List["ComponentInput"]


@strawberry.input
class ComponentInput:
    key: str
    configuration: strawberry.scalars.JSON
