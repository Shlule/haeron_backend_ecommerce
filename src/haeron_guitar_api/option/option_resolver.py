import strawberry
from uuid import UUID
from typing import List, Optional

from ..models import Option
from .option_dto import CreateOptionDTO
from .option_input import CreateOptionInput, OptionFilterInput
from .option_service import OptionService
from .option_filter import OptionFilterSet


from ..types.types import OptionGQLType
from authUser.permission.permission import HasRole, IsAuthenticated


@strawberry.type
class OptionQuery:
    @strawberry.field(permission_classes=[IsAuthenticated, HasRole("superadmin","admin", "production_manager","rnd")])
    def options(self, filters: Optional[OptionFilterInput] = None) -> OptionGQLType:
        qs = Option.objects.all()
        if filters:
            filter_dict = {k: v for k, v in filters.__dict__.items() if v is not None}
            qs = OptionFilterSet(filter_dict, queryset=qs).qs
        return qs


@strawberry.type
class OptionMutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated, HasRole("superadmin","admin", "rnd")])
    def create_option(self, input: CreateOptionInput) -> OptionGQLType:
        dto = CreateOptionDTO(
            input.name,
            input.description,
        )
        option = OptionService.create(dto)
        return option

    # TODO - make some mutation to delete with name  or code  because they're unique see models
    @strawberry.mutation(permission_classes=[IsAuthenticated, HasRole("superadmin","admin", "rnd")])
    def delete_options(self, option_ids: List[UUID]) -> bool:
        return OptionService.delete(option_ids)


OptionQuery = OptionQuery
OptionMutation = OptionMutation
