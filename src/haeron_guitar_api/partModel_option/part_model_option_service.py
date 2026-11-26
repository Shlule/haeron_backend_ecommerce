from django.core.exceptions import ValidationError
from ..models import PartModelOption, PartModel, Option
from .part_model_option_dto import (
    CreatePartModelOptionDTO,
    UpdatePartModelOptionActiveDTO,
    UpdatePartModelOptionPriceDTO,
)


class PartModelOptionService:
    @staticmethod
    def create(dto: CreatePartModelOptionDTO) -> PartModelOption:

        part_model = PartModel.objects.filter(pk=dto.part_model).first()
        if not part_model:
            raise ValidationError("PartModel not found")

        option = Option.objects.filter(pk=dto.option).first()
        if not option:
            raise ValidationError("Option not found")

        code = dto.code.strip()
        if not code:
            raise ValidationError("Code is required")

        # an option has several values on a part model (color_red, color_blue...), but each value only once
        if PartModelOption.objects.filter(part_model=part_model, option=option, code=code).exists():
            raise ValidationError(f"Value {code} already exists for {option.name} on this PartModel")

        return PartModelOption.objects.create(
            name=dto.name.strip() or code,
            code=code,
            part_model=part_model,
            option=option,
            price_delta=dto.price_delta or 0,
        )

    @staticmethod
    def update_price(dto: UpdatePartModelOptionPriceDTO) -> PartModelOption:
        pmo = PartModelOption.objects.filter(pk=dto.uuid).first()
        if not pmo:
            raise ValidationError("PartModelOption not found")

        if dto.price_delta is not None:
            pmo.price_delta = dto.price_delta

        pmo.save()
        return pmo

    @staticmethod
    def set_active(dto: UpdatePartModelOptionActiveDTO) -> PartModelOption:
        pmo = PartModelOption.objects.filter(pk=dto.uuid).first()
        if not pmo:
            raise ValidationError("PartModelOption not found")

        pmo.is_active = dto.is_active
        pmo.save(update_fields=["is_active", "updated_at"])
        return pmo
