import strawberry_django
from strawberry import ID
from typing import Optional, List
from uuid import UUID
from datetime import date

from . import models

from authUser.models import User as CustomUser


@strawberry_django.interface
class AuditInterface:
    created_at: str
    updated_at: str
    created_by: Optional["UserGQLType"]
    updated_by: Optional["UserGQLType"]


@strawberry_django.type(models.SerialCounter)
class SerialCounterGQLType:
    uuid: ID
    factory: "FactoryGQLType"
    date: date
    last_value: int


@strawberry_django.type(models.Series)
class SeriesGQLType:
    uuid: ID
    code: str
    name: str


@strawberry_django.type(models.Factory)
class FactoryGQLType:
    uuid: ID
    code: str
    name: str


@strawberry_django.type(models.Option)
class OptionGQLType:
    uuid: ID
    name: str
    description: str


@strawberry_django.type(models.PartType)
class PartTypeGQLType:
    uuid: ID
    name: str
    code: str
    instrument_types: List["InstrumentTypeGQLType"]


@strawberry_django.type(models.PartModelOption)
class PartModelOptionGQLType:
    uuid: ID
    name: str
    code: str
    part_model: "PartModelGQLType"
    option: "OptionGQLType"
    price_delta = float


@strawberry_django.type(models.PartModel)
class PartModelGQLType:
    uuid: ID
    name: str
    price: float
    part_type: PartTypeGQLType
    series: Optional["SeriesGQLType"]
    code: str


@strawberry_django.type(models.PartHistory)
class PartHistoryGQLType:
    uuid: ID
    event_type: str
    title: str
    description: str
    timestamp: str
    user: Optional["UserGQLType"]
    part: "PartGQLType"


@strawberry_django.type(models.Part)
class PartGQLType:
    uuid: ID
    serial_number: str
    auth_key: Optional[str]
    part_model: PartModelGQLType
    auth_key: str
    part_history: Optional[List["PartHistoryGQLType"]]
    is_master: bool


@strawberry_django.type(models.InstrumentHistory)
class InstrumentHistoryGQLType:
    uuid: ID
    instrument: "InstrumentGQLType"
    event_type: str
    title: str
    description: str
    timestamp: str
    user: Optional["UserGQLType"]


@strawberry_django.type(models.InstrumentType)
class InstrumentTypeGQLType:
    uuid: ID
    code: str
    name: str
    part_types: List["PartTypeGQLType"]


@strawberry_django.type(models.Instrument)
class InstrumentGQLType:
    parts: List["PartGQLType"]
    uuid: UUID
    owner: Optional["UserGQLType"]
    master_part: "PartGQLType"
    instrument_type: "InstrumentTypeGQLType"


@strawberry_django.type(CustomUser)
class UserGQLType:
    uuid: ID
    intruments: List["InstrumentGQLType"]


@strawberry_django.type(models.Cart)
class CartGQLType:
    uuid: ID
    user: "UserGQLType"
    session_key: str
    expires_at: date
    last_activity_at: date
    create_at: date
    is_active: bool


@strawberry_django.type(models.CartItem)
class CartItemGQLType:
    uuid: ID
    cart: "CartGQLType"
    product: "ProductGQLType"
    quantity: int
    unit_price: float
    configuration_snapshot: dict


@strawberry_django.type(models.CartItemOption)
class CartItemOptionGQLType:
    uuid: ID
    option = "PartModelOptionGQLType"
    price_delta: float


@strawberry_django.type(models.Product)
class ProductGQLType:
    uuid: ID
    name: str
    price: float
    part_model: "PartModelGQLType"
