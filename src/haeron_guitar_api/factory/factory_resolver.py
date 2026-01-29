import strawberry
from uuid import UUID
from typing import List

from ..models import Factory

from .factory_dto import CreateFactoryDTO
from .factory_input import CreateFactoryInput
from .factory_service import FactoryService
from ..types import FactoryGQLType

@strawberry.type
class FactoryQuery:
    @strawberry.field
    def get_factory(self, uuid: UUID) -> FactoryGQLType:
        instrument_type = Factory.objects.get(pk=uuid)
        return instrument_type
    
    @strawberry.field
    def get_all_factory() -> List[FactoryGQLType]:
        return Factory.objects.all()
    

@strawberry.type
class FactoryMutation:
    @strawberry.mutation
    def create_factory(self, input: CreateFactoryInput) -> FactoryGQLType:
        dto = CreateFactoryDTO(
            input.name,
            input.code,
        )
        factory = FactoryService.create(dto)
        return factory

FactoryMutation = FactoryMutation
FactoryQuery = FactoryQuery