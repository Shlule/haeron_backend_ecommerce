from typing import List
from uuid import UUID
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist
from ..models import PartModel, PartType, Series, Option, PartModelOption
from .part_model_dto import CreatePartModelDTO, UpdatePartModelDTO


class PartModelService:
    @staticmethod
    def create(dto: CreatePartModelDTO) -> PartModel:
        try:
            part_type = PartType.objects.get(pk=dto.part_type_id)
        except PartType.DoesNotExist:
            raise ValueError(f"PartType {dto.part_type_id} does not exist")

        series = None
        if dto.series_id:
            try:
                series = Series.objects.get(pk=dto.series_id)
            except Series.DoesNotExist:
                raise ValueError(f"Series {dto.series_id} does not exist")

        part_model = PartModel.objects.create(
            name=dto.name, part_type=part_type, series=series, price=dto.price, code=dto.code
        )

        return part_model

    @staticmethod
    def update(dto: UpdatePartModelDTO) -> PartModel:

        part_model = PartModel.objects.get(pk=dto.uuid)

        if dto.name is not None:
            part_model.name = dto.name

        if dto.part_type_id is not None:
            part_type = PartType.objects.get(pk=dto.part_type_id)
            part_model.part_type = part_type

        if dto.code is not None:
            part_model.code = dto.code

        if dto.price is not None:
            part_model.price = dto.price

        if dto.series_id is not None:
            part_model.series = Series.objects.get(pk=dto.series_id)

        if dto.compatible_options_ids is not None:
            options = Option.objects.filter(uid__in=dto.compatible_options_ids)
            # Vérifie que tous les IDs donnés existent
            if len(options) != len(dto.compatible_options_ids):
                missing_ids = set(dto.compatible_options_ids) - set(o.uid for o in options)
                raise ValueError(f"Options not found: {missing_ids}")
            part_model.compatible_options.set(options)

        part_model.save()
        return part_model
