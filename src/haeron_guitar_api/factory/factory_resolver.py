import strawberry
from uuid import UUID
from typing import List

from ..models import Factory

from .factory_dto import CreateFactoryDTO
from .factory_input import CreateFactoryInput
from .factory_service import FactoryService
from ..types.types import FactoryGQLType
from authUser.permission.permission import HasRole, IsAuthenticated


@strawberry.type
class FactoryQuery:
    @strawberry.field(permission_classes=[IsAuthenticated, HasRole("superadmin","admin")])
    def get_factory(self, uuid: UUID) -> FactoryGQLType:
        instrument_type = Factory.objects.get(pk=uuid)
        return instrument_type

    @strawberry.field(permission_classes=[IsAuthenticated, HasRole("superadmin", "admin")])
    def get_all_factory() -> List[FactoryGQLType]:
        return Factory.objects.all()


@strawberry.type
class FactoryMutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated, HasRole("superadmin")])
    def create_factory(self, input: CreateFactoryInput) -> FactoryGQLType:
        dto = CreateFactoryDTO(
            name=input.name,
            code=input.code,
        )
        factory = FactoryService.create(dto)
        return factory

    @strawberry.mutation(permission_classes=[IsAuthenticated, HasRole("superadmin")])
    def delete_factories(self, factory_ids: List[UUID]) -> int:
        delete_count = FactoryService.delete(factory_ids)
        return delete_count


FactoryMutation = FactoryMutation
FactoryQuery = FactoryQuery
