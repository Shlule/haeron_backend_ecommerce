import strawberry
from uuid import UUID
from typing import List

from ..models import PartModel
from ..types.types import PartModelGQLType
from .part_model_input import CreatePartModelInput, UpdatePartModelInput
from .part_model_dto import CreatePartModelDTO, UpdatePartModelDTO
from .part_model_service import PartModelService
from authUser.permission.permission import HasRole, IsAuthenticated


@strawberry.type
class PartModelQuery:
    @strawberry.field(permission_classes=[IsAuthenticated, HasRole("superadmin","admin", "rnd", "production_manager")])
    def get_part_model(self, uuid: UUID) -> PartModelGQLType:
        return PartModel.objects.get(uuid)

    @strawberry.field(permission_classes=[IsAuthenticated, HasRole("superadmin","admin", "rnd", "production_manager")])
    def get_all_part_model(self) -> List[PartModelGQLType]:
        return PartModel.objects.all()


@strawberry.type
class PartModelMutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated, HasRole("superadmin","admin", "rnd")])
    def create_part_model(self, input: CreatePartModelInput) -> PartModelGQLType:
        dto = CreatePartModelDTO(
            name=input.name,
            code=input.code,
            part_type_id=input.part_type_id,
            series_id=input.series_id,
            price=input.price,
        )
        return PartModelService.create(dto)

    @strawberry.mutation(permission_classes=[IsAuthenticated, HasRole("superadmin","admin", "rnd")])
    def update_part_model(self, uuid: UUID, input: UpdatePartModelInput) -> PartModelGQLType:
        dto = UpdatePartModelDTO(
            name=input.name,
            part_type_id=input.part_type_id,
            series_id=input.series_id,
            price=input.price,
            code=input.code,
        )
        return PartModelService.update(dto)


PartModelQuery = PartModelQuery
PartModelMutation = PartModelMutation
