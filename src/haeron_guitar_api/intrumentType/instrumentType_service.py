from django.db import IntegrityError, transaction
from ..models import InstrumentType, PartType
from .instrumentType_dto import CreateInstrumentTypeDTO
from typing import List
from uuid import UUID


class InstrumentTypeService:
    @staticmethod
    def create(dto: CreateInstrumentTypeDTO) -> InstrumentType:
        try:
            with transaction.atomic():
                instrument_type = InstrumentType.objects.create(name=dto.name, code=dto.code)

                if hasattr(dto, "part_types") and dto.part_types:
                    parts = PartType.objects.filter(uuid__in=dto.part_types)
                    instrument_type.part_types.add(*parts)

            return instrument_type

        except IntegrityError as e:
            raise ValueError("InstrumentType with the same name or code already exists")

    @staticmethod
    def add_parts_types(instrument_type_id: UUID, part_types_ids: List[UUID]) -> bool:
        try:
            instrument_type = InstrumentType.objects.get(pk=instrument_type_id)
        except InstrumentType.DoesNotExist:
            raise ValueError("Instrument type does not exist")
        parts = PartType.objects.filter(pk__in=part_types_ids)
        if len(parts) != len(part_types_ids):
            raise ValueError(" Some Part_Type UUID's does not exist")

        with transaction.atomic():
            instrument_type.part_types.add(*parts)

        return True

    @staticmethod
    def remove_parts_types(instrument_type_id: UUID, part_types_ids: List[UUID]) -> bool:
        try:
            instrument_type = InstrumentType.objects.get(pk=instrument_type_id)
        except InstrumentType.DoesNotExist:
            raise ValueError("Instrument type does not exist")

        parts = PartType.objects.filter(pk__in=part_types_ids)
        if len(parts) != len(part_types_ids):
            raise ValueError(" Some Part_Type UUID's does not exist")

        with transaction.atomic():
            instrument_type.part_types.remove(*parts)

        return True
