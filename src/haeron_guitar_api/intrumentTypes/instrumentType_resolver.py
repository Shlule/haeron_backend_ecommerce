import strawberry
from uuid import UUID
from typing import List

from ..models import InstrumentType

from .instrumentType_dto import CreateInstrumentTypeDTO
from .instrumentType_input import CreateInstrumentTypeInput
from .instrumentType_service import InstrumentTypeService
from ..types import InstrumentTypeGQLType

@strawberry.type
class InstrumentTypeQuery:
    @strawberry.field
    def get_instrument_type(self, uuid: UUID) -> InstrumentTypeGQLType:
        instrument_type = InstrumentType.objects.get(pk=uuid)
        return instrument_type
    
    @strawberry.field
    def get_all_instrument_type(self) -> List[InstrumentTypeGQLType]:
        return InstrumentType.objects.all()

@strawberry.type
class InstrumentTypeMutation:
    @strawberry.mutation
    def create_instrument_type(self, input: CreateInstrumentTypeInput) -> InstrumentTypeGQLType:
        print("helloe")
        dto = CreateInstrumentTypeDTO(
            input.name,
            input.code,
        )
        print(dto)
        instrument_type = InstrumentTypeService.create(dto)
        return instrument_type
    
InstrumentTypeQuery = InstrumentTypeQuery
InstrumentTypeMutation = InstrumentTypeMutation