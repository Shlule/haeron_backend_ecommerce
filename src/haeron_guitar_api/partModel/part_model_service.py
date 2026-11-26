from haeron_guitar_api.security.vault.vault_factory import get_vault_service
from ..models import PartModel, PartType, Series
from .part_model_dto import CreatePartModelDTO, UpdatePartModelDTO
from django.db import transaction
from django.utils import timezone


class PartModelService:
    @staticmethod
    @transaction.atomic
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
        get_vault_service().post_secret("domain", part_model_id = str(part_model.uuid))

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

        if dto.status is not None and dto.status != part_model.status:
            statuses = [value for value, _ in PartModel._meta.get_field("status").choices]
            if dto.status not in statuses:
                raise ValueError(f"Unknown status {dto.status}, expected one of {statuses}")
            part_model.status = dto.status
            # date at which the model stopped being sold, cleared if it is sold again
            if dto.status in ("service_only", "discontinued"):
                part_model.discontinued_at = part_model.discontinued_at or timezone.now()
            else:
                part_model.discontinued_at = None

        part_model.save()
        return part_model
