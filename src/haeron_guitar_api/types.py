import strawberry_django
from strawberry import ID
from typing import Optional, List
from uuid import UUID

from . import models

from authUser.models import User as CustomUser


@strawberry_django.interface
class AuditInterface: 
    created_at: str
    updated_at: str
    created_by: Optional["UserGQLType"]
    updated_by: Optional["UserGQLType"]


@strawberry_django.type(models.Series)


@strawberry_django.type(models.SerialCounter)
class SerialCounterGQLType:
    id: ID
    key: str
    last_value: int


@strawberry_django.type(models.Series)
class SeriesGQLType:
    id:ID
    code: str
    name: str


@strawberry_django.type(models.Factory)
class FactoryGQLType:
    id:ID
    code: str
    name: str
    city: str


@strawberry_django.type(models.Option)
class OptionGQLType: 
    id: ID
    name: str
    description: str


@strawberry_django.type(models.PartType)
class PartTypeGQLType:
    id: ID
    name: str
    code: str


@strawberry_django.type(models.PartModelOption)
class PartModelOptionGQLType:
    id: ID
    part_model: "PartModelGQLType"
    option: "OptionGQLType"
    price_delta = float


@strawberry_django.type(models.PartModel)
class PartModelGQLType:
    id: ID 
    name: str
    price: float
    part_type: PartTypeGQLType
    series: Optional["SeriesGQLType"]
    code: str


@strawberry_django.type(models.PartHistory)
class PartHistoryGQLType:
    id: ID
    event_type: str
    title: str
    description: str
    timestamp: str
    user: Optional["UserGQLType"]
    part: "PartGQLType"


@strawberry_django.type(models.Part)
class PartGQLType:
    id: ID
    serial_number: str
    part_model: PartModelGQLType
    auth_key: str
    part_history: List["PartHistoryGQLType"]
    is_master: bool


@strawberry_django.type(models.InstrumentHistory)
class InstrumentHistoryGQLType: 
    id: ID
    instrument: "InstrumentGQLType"
    event_type: str
    title: str
    description: str
    timestamp: str
    user: Optional["UserGQLType"]


@strawberry_django.type(models.InstrumentType)
class InstrumentTypeGQLType:
    id:ID
    code: str
    name: str


@strawberry_django.type(models.Instrument)
class InstrumentGQLType:
    parts: List["PartGQLType"]
    uid: UUID
    owner: Optional["UserGQLType"]
    master_part: "PartGQLType"
    instrument_type: "InstrumentTypeGQLType"

    
@strawberry_django.type(CustomUser)
class UserGQLType:
    id: ID
    intruments: List["InstrumentGQLType"]

    
    