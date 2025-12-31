from django.db import IntegrityError
from ..models import Factory
from .factory_dto import CreateFactoryDTO

class FactoryService:
    @staticmethod
    def create(self, dto: CreateFactoryDTO) ->Factory:
        try: 
            factory = Factory.objects.create(
                name=dto.name,
                code=dto.code
            )

        except IntegrityError as e:
            raise ValueError("factory with the same name or code already exists")

