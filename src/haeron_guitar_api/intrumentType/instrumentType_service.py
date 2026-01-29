from django.db import IntegrityError
from ..models import InstrumentType
from .instrumentType_dto import CreateInstrumentTypeDTO

class InstrumentTypeService:
    @staticmethod
    def create(dto: CreateInstrumentTypeDTO) -> InstrumentType:
        try: 
            intrument_type = InstrumentType.objects.create(
                name=dto.name,
                code=dto.code
            )

            return intrument_type

        except IntegrityError as e:
            raise ValueError("InstrumentType with the same name or code already exists")

