from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from models import PartHistory
from .part_history_dto import CreatePartHistoryDTO, UpdatePartHistoryDTO

class PartHistoryService:

    @staticmethod
    def create(dto: CreatePartHistoryDTO) -> PartHistory:
        part = get_object_or_404(PartHistory, uuid=dto.part)

        part_history = PartHistory.objects.create(
            description = dto.description,
            title = dto.title,
            event_type = dto.event_type,
            part = dto.part,
        )

        return part_history
    
    def update(parthistory: PartHistory, dto:UpdatePartHistoryDTO) -> PartHistory:
        if dto.description is not None: 
            parthistory.description = dto.description

        if dto.event_type is not None:
            parthistory.event_type = dto.event_type

        if dto.title is not None:
            parthistory.title = dto.title

        if dto.part is not None:
            parthistory.part = get_object_or_404(PartHistory, uuid = dto.part)

        parthistory.save()
        return parthistory