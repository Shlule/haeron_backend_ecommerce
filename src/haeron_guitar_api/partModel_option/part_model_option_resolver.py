from itertools import count
import strawberry
from uuid import UUID
from typing import List

from ..types import PartModelOptionGQLType
from ..models import PartModelOption

from .part_model_option_dto import CreatePartModelOptionDTO, UpdatePartModelOptionPriceDTO
from .part_model_option_input import (
    CreatePartModelOptionInput,
    UpdatePartModelOptionPriceInput,
    PartModelOptionInputFilter,
)
from .part_model_option_service import PartModelOptionService
from .part_model_option_filter import PartModelOptionFIlterSet


@strawberry.type
class PartModelOptionQuery:
    @strawberry.field
    def partModelOptions(self, filters: PartModelOptionInputFilter) -> PartModelOptionGQLType:
        qs = PartModelOption.objects.all()
        if filters:
            filter_dict = {k: v for k, v in filters.__dict__.items() if v is not None}
            qs = PartModelOptionFIlterSet(filter_dict, queryset=qs).qs
        return qs

    @strawberry.field
    def get_all_part_model_options(self) -> List[PartModelOptionGQLType]:
        return PartModelOption.objects.all()


@strawberry.type
class PartModelOptionMutation:
    @strawberry.mutation
    def create_part_model_option(self, input: CreatePartModelOptionInput) -> PartModelOptionGQLType:
        dto = CreatePartModelOptionDTO(
            name=input.name,
            code=input.code,
            part_model=input.part_model,
            option=input.option,
            price_delta=input.price_delta,
        )
        part_model_option = PartModelOptionService.create(dto)
        return part_model_option

    @strawberry.mutation
    def update_price(self, input: UpdatePartModelOptionPriceInput) -> PartModelOptionGQLType:
        dto = UpdatePartModelOptionPriceDTO(uuid=input.uuid, price_delta=input.price_delta)
        return PartModelOptionService.update_price(dto)

    @strawberry.mutation
    def delete_part_model_options(self, part_model_options_ids: List[UUID]) -> bool:
        delete_count, _ = PartModelOption.objects.filter(pk__in=part_model_options_ids).delete()
        return delete_count


PartModelOptionMutation = PartModelOptionMutation
PartModelOptionQuery = PartModelOptionQuery
