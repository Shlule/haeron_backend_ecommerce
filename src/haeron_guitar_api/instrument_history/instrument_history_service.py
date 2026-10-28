from django.shortcuts import get_object_or_404

from ..models import InstrumentHistory
from .instrument_history_dto import CreateInstrumentHistoryDTO, UpdateInstrumentHistoryDTO 

class InstrumentHistoryService:

    @staticmethod
    def create(dto: CreateInstrumentHistoryDTO) -> InstrumentHistory:
        instrument = get_object_or_404(InstrumentHistory, uuid=dto.part)

        instrument_history = InstrumentHistory.objects.create(
            description = dto.description,
            title = dto.title,
            event_type = dto.event_type,
            part = dto.instrument,
        )

        return instrument_history
    
    def update(instruemnt_history: InstrumentHistory, dto:UpdateInstrumentHistoryDTO) -> InstrumentHistory:
        if dto.description is not None: 
            instruemnt_history.description = dto.description

        if dto.event_type is not None:
            instruemnt_history.event_type = dto.event_type

        if dto.title is not None:
            instruemnt_history.title = dto.title

        if dto.instrument is not None:
            instruemnt_history.instrument = get_object_or_404(InstrumentHistory, uuid = dto.part)

        instruemnt_history.save()
        return instruemnt_history