import strawberry
from uuid import UUID
from typing import List

from ..types import PartModelOptionGQLType
from ..models import PartModelOption

from .part_model_option_dto import CreatePartModelOptionDTO, UpdatePartModelOptionPriceDTO
from .part_model_option_input import CreatePartModelOptionInput, UpdatePartModelOptionPriceInput
from .part_model_option_service import PartModelOptionService


@strawberry.type
class PartModelOptionQuery:
    @strawberry.field
    def partModelOption(self, uuid: UUID) -> PartModelOptionGQLType:
        part_model_option = PartModelOption.objects.get(pk=uuid)
        return part_model_option

    @strawberry.field
    def get_all_part_model_options(self) -> List[PartModelOptionGQLType]:
        return PartModelOption.objects.all()


@strawberry.type
class PartModelOptionMutation:
    @strawberry.mutation
    def create_part_model_option(self, input: CreatePartModelOptionInput) -> PartModelOptionGQLType:
        dto = CreatePartModelOptionDTO(
            input.part_model,
            input.option,
            input.price_delta,
        )
        part_model_option = PartModelOptionService.create(dto)
        return part_model_option

    @strawberry.mutation
    def update_price(self, input: UpdatePartModelOptionPriceInput) -> PartModelOptionGQLType:
        dto = UpdatePartModelOptionPriceDTO(uuid=input.uuid, price_delta=input.price_delta)
        return PartModelOptionService.update_price(dto)


PartModelOptionMutation = PartModelOptionMutation
PartModelOptionQuery = PartModelOptionQuery
