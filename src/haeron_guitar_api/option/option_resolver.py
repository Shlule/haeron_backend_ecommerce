import strawberry
from uuid import UUID
from typing import List

from ..models import Option
from .option_dto import CreateOptionDTO
from .option_input import CreateOptionInput
from .option_service import OptionService

from ..types import OptionGQLType


@strawberry.type
class OptionQuery:
    @strawberry.field
    def options(self, uuid: UUID) -> OptionGQLType:
        option = Option.objects.get(pk=uuid)
        return option


@strawberry.type
class OptionMutation:
    @strawberry.mutation
    def create_option(self, input: CreateOptionInput) -> OptionGQLType:
        dto = CreateOptionDTO(
            input.name,
            input.description,
        )
        option = OptionService.create(dto)
        return option

    # TODO - make some mutation to delete with name  or code  because they're unique see models
    @strawberry.mutation
    def delete_options(self, option_ids: List[UUID]) -> bool:
        return OptionService.delete(option_ids)


OptionQuery = OptionQuery
OptionMutation = OptionMutation
