from django.db import IntegrityError
from ..models import PartType
from .partType_dto import CreatePartTypeDTO

class PartTypeService:
    @staticmethod
    def create(dto: CreatePartTypeDTO) -> PartType:
        try: 
            PartType.objects.create(
                name=dto.name,
                code=dto.code
            )
            
        except IntegrityError as e:
            raise ValueError("PartType with the same name or code already exists")