from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from ..models import Part, PartModel 
from .part_dto import CreatePartDTO, UpdatePartDTO

User = get_user_model()

class PartService:
    
    @staticmethod
    def create(dto: CreatePartDTO) -> Part:
        part_model = get_object_or_404(PartModel, uuid=dto.part_model_id)

        owner = None
        if dto.owner_id:
            owner = get_object_or_404(User, uuid=dto.owner_id)
            
        part = Part.objects.create(
            serial_number = dto.serial_number,
            auth_key = dto.auth_key,
            part_model = part_model,
            owner = owner, 
            is_master = dto.is_master,
        )

        return part
    
    @staticmethod
    def update(part: Part, dto: UpdatePartDTO) -> Part:
        if dto.serial_number is not None:
            part.serial_number = dto.serial_number

        if dto.auth_key is not None:
            part.auth_key = dto.auth_key

        if dto.part_model_id is not None:
            part.part_model = get_object_or_404(PartModel, uid=dto.part_model_id)

        if dto.owner_id is not None:
            part.owner = get_object_or_404(User, uid=dto.owner_id)

        if dto.is_master is not None:
            part.is_master = dto.is_master

        part.save()
        return part
