import strawberry
from uuid import UUID
from typing import List

from ..models import PartHistory
from ..types import PartHistoryGQLType
from .part_history_input import CreatePartHistoryInput, UpdatePartHistoryInput
from .part_history_dto import CreatePartHistoryDTO, UpdatePartHistoryDTO
from .part_history_service import PartHistoryService

@strawberry.type
class PartHistoryQuery:
    @strawberry.field
    def get_part_history(self, uuid: UUID) -> PartHistoryGQLType:
        return PartHistory.objects.get(uuid)
    
    @strawberry.field
    def get_all_history(self) -> List[PartHistoryGQLType]:
        return PartHistory.objects.all()
    
@strawberry.type
class PartHistoryMutation:
    @strawberry.mutation
    def create_part_history(self, input:CreatePartHistoryInput) -> PartHistoryGQLType:
        dto = CreatePartHistoryDTO(
            title=input.title,
            description=input.description,
            event_type=input.event_type,
            part=input.part,
        )
        return PartHistoryService.create(dto)
    
    @strawberry.mutation
    def update_part_history(self, uuid: UUID, input:UpdatePartHistoryInput) -> PartHistoryGQLType:
        part_history = PartHistory.objects.get(uuid)
        dto = UpdatePartHistoryDTO(
            event_type=input.event_type,
            title=input.title,
            description=input.description,
            part=input.part,
        )
        return PartHistoryService.update(part_history, dto)
    
PartHistoryQuery = PartHistoryQuery
PartHistoryMutation = PartHistoryMutation