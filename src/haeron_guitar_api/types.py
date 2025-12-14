import strawberry_django
from strawberry import ID
from typing import Optional, List
from uuid import UUID

from . import models




@strawberry_django.type(models.Option)
class OptionGQLType: 
    id: ID
    name: str
    description: str



@strawberry_django.type(models.PartType)
class PartTypeGQLType:
    id: ID
    name: str


@strawberry_django.type(models.PartModelOption)
class PartModelOptionGQLType:
    id: ID
    part_model: "PartModelGQLType"
    option: "OptionGQLType"
    price_delta = float


@strawberry_django.type(models.PartModel)
class PartModelGQLType: 
    name: str
    price: float
    part_type: PartTypeGQLType
    series: Optional["SeriesGQLType"]


@strawberry_django.type(models.PartHistory)
class PartHistoryGQLType:
    event_type: str
    title: str
    description: str
    timestamp: str
    user: Optional["UserGQLType"]
    part: "PartGQLType"


@strawberry_django.type(models.Part)
class PartGQLType: 
    serial_number: str
    part_model: PartModelGQLType
    auth_key: str
    part_history: List["PartHistoryGQLType"]


@strawberry_django.type(models.InstrumentHistory)
class InstrumentHistoryGQLType: 
    id: ID
    instrument: "InstrumentGQLType"
    event_type: str
    title: str
    description: str
    timestamp: str
    user: Optional["UserGQLType"]


@strawberry_django.type(models.Instrument)
class InstrumentGQLType:
    parts: List["PartGQLType"]
    auth_key: str
    uid: UUID
    serial_number: str
    owner: Optional["UserGQLType"]

    
@strawberry_django.type(models.User)
class UserGQLType:
    id: ID
    intruments: List["InstrumentGQLType"]

    
    