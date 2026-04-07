from django.db import IntegrityError, transaction
from ..models import PartType, InstrumentType
from .partType_dto import CreatePartTypeDTO
from uuid import UUID
from typing import List


class PartTypeService:
    @staticmethod
    def create(dto: CreatePartTypeDTO) -> PartType:
        try:
            with transaction.atomic():
                part_type = PartType.objects.create(name=dto.name, code=dto.code)

            return part_type
        except IntegrityError as e:
            raise ValueError("PartType with the same name or code already exists")

    @staticmethod
    def add_instruments_types(part_type_id: UUID, instrument_types_ids: List[UUID]) -> bool:
        print("%" * 50)
        print("je suis dans le service")
        try:
            part_type = PartType.objects.get(pk=part_type_id)
        except PartType.DoesNotExist:
            raise ValueError("PartType does not exist")

        instruments = InstrumentType.objects.filter(pk__in=instrument_types_ids)
        if len(instruments) != len(instrument_types_ids):
            raise ValueError("Some Instrument Type UUID's do not exist")

        with transaction.atomic():
            part_type.instrument_types.add(*instruments)
        return True

    @staticmethod
    def remove_instruments_types(part_type_id: UUID, instrument_types_ids: List[UUID]) -> bool:
        try:
            part_type = PartType.objects.get(pk=part_type_id)
        except PartType.DoesNotExist:
            raise ValueError("PartType does not exist")

        instruments = InstrumentType.objects.filter(pk__in=instrument_types_ids)
        if len(instruments) != len(instrument_types_ids):
            raise ValueError("Some InstrumentType UUIDs do not exist")

        with transaction.atomic():
            part_type.instrument_types.remove(*instruments)

        return True
