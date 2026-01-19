from django.db import IntegrityError
from ..models import Option
from .option_dto import CreateOptionDTO

class OptionService: 
    @staticmethod
    def create(dto: CreateOptionDTO) -> Option:
        try:
            option = Option.objects.create(
                name=dto.name,
                description = dto.description,
            )
        except IntegrityError as e:
            raise ValueError("Cannot create the option")