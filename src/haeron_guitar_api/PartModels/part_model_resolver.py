import strawberry
from uuid import UUID
from typing import List

from ..models import PartModel
from ..types import PartModelGQLType
from .part_model_input import CreatePartModelInput, UpdatePartModelInput
from .part_model_dto import CreatePartModelDTO, UpdatePartModelDTO
from .part_model_service import PartModelService

@strawberry.type
class PartModelQuery:
    @strawberry.field
    def get_part_model(self, uuid: UUID) -> PartModelGQLType:
        return PartModel.objects.get(uuid)
    
    @strawberry.field
    def get_all_part_model(self) -> List[PartModelGQLType]:
        return PartModel.objects.all()

@strawberry.type
class PartModelMutation:
    @strawberry.mutation
    def create_part_model(self, input: CreatePartModelInput) -> PartModelGQLType:
        dto = CreatePartModelDTO(
            name=input.name,
            code=input.code,
            part_type_id=input.part_type_id,
            series_id=input.series_id,
            price=input.price,
            compatible_options_id=input.compatibles_options_ids
        )
        return PartModelService.create(dto)
    
    @strawberry.mutation
    def update_part_model(self, uuid: UUID, input: UpdatePartModelInput) -> PartModelGQLType:
        part_model = PartModel.objects.get(uuid = uuid)
        dto = UpdatePartModelDTO(
           name=input.name,
           part_type_id=input.part_type_id,
           series_id=input.series_id,
           compatibles_options_ids=input.compatibles_options_ids,
           price=input.price,
           code=input.code,
        )
        return PartModelService.update(dto)
    
PartModelQuery = PartModelQuery
PartModelMutation = PartModelMutation