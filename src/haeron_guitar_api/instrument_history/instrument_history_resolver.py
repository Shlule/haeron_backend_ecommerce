import strawberry
from uuid import UUID
from typing import List

from ..models import InstrumentHistory
from ..types import InstrumentHistoryGQLType
from .instrument_history_dto import CreateInstrumentHistoryDTO, UpdateInstrumentHistoryDTO
from .instrument_history_input import CreateInstrumentHistoryInput, UpdateInstrumentHistoryInput
from .instrument_history_service import InstrumentHistoryService

@strawberry.type
class InstrumentHistoryQuery:
    @strawberry.field
    def get_instrument_history(self, uuid: UUID) -> InstrumentHistoryGQLType:
        return InstrumentHistory.objects.get(uuid)

    def get_all_instrument_history(self) -> List[InstrumentHistoryGQLType]:
        return InstrumentHistory.objects.all()
    

@strawberry.type
class InstrumentHistoryMutation:
    @strawberry.mutation
    def create_instrument_history(self, input:CreateInstrumentHistoryInput) -> InstrumentHistoryGQLType:
        dto = CreateInstrumentHistoryDTO(
            title=input.title,
            description=input.description,
            event_type=input.event_type,
            instrument=input.instrument,
        )
        return InstrumentHistoryService.create(dto)
    
    @strawberry.mutation
    def update_instrument_history(self, uuid:UUID, input: UpdateInstrumentHistoryInput) -> InstrumentHistoryGQLType:
        instrument_history = InstrumentHistory.objects.get(uuid)
        dto = CreateInstrumentHistoryDTO(
            title=input.title,
            description=input.description,
            event_type=input.event_type,
            instrument=input.instrument,
        )
        return InstrumentHistoryService.update(instrument_history, dto)

InstrumentHistoryQuery = InstrumentHistoryQuery
InstrumentHistoryMutation = InstrumentHistoryMutation