from django.core.exceptions import ValidationError
from ..models import PartModelOption, PartModel, Option
from .part_model_option_dto import CreatePartModelOptionDTO, UpdatePartModelOptionPriceDTO


class PartModelOptionService:
    @staticmethod
    def create(dto: CreatePartModelOptionDTO) -> PartModelOption:

        part_model = PartModel.objects.filter(pk=dto.part_model_id).first()
        if not part_model:
            raise ValidationError("PartModel not found")

        option = Option.objects.filter(pk=dto.option_id).first()
        if not option:
            raise ValidationError("Option not found")

        if PartModelOption.objects.filter(part_model=part_model, option=option).exists():
            raise ValidationError("Option already linked to this PartModel")

        return PartModelOption.objects.create(part_model=part_model, option=option, price_delta=dto.price_delta)

    @staticmethod
    def update_price(dto: UpdatePartModelOptionPriceDTO) -> PartModelOption:
        pmo = PartModelOption.objects.filter(pk=dto.uuid).first()
        if not pmo:
            raise ValidationError("PartModelOption not found")

        if dto.price_delta is not None:
            pmo.price_delta = dto.price_delta

        pmo.save()
        return pmo
