import strawberry
from uuid import UUID
from typing import List

from ..models import Instrument

from .instrument_input import CreateInstrumentInput 
from .instrument_dto import CreateInstrumentDTO
from .Instrument_service import create_instrument
from ..types import InstrumentGQLType

@strawberry.type
class InstrumentQuery:
    @strawberry.field
    def get_instrument(self, uuid: UUID) -> InstrumentGQLType :
        intrument = Instrument.objects.get(pk=uuid)
        return intrument
    @strawberry.field
    def get_all_instruments(self) -> List[InstrumentGQLType]:
        return Instrument.objects.all()

    
@strawberry.type
class InstrumentMutation: 
    @strawberry.mutation
    def create_instrument(self, input: CreateInstrumentInput) -> InstrumentGQLType:
        dto = CreateInstrumentDTO(
            input.instrument_type_id,
            input.owner_id,
            input.master_part_id,
            input.parts_id
        )
        instrument = create_instrument(dto)
        return instrument
        
# @strawberry.mutation
# def create_instrument(self, input: CreateInstrumentInput) -> InstrumentGQLType:
#     # Transformation directe Input → DTO
#     dto = CreateInstrumentDTO(
#         instrument_type_id=UUID(str(input.instrument_type_id)),
#         owner_id=UUID(str(input.owner_id)) if input.owner_id else None,
#         master_part_id=UUID(str(input.master_part_id)),
#         parts_ids=[UUID(str(pid)) for pid in input.parts_ids]
#     )
    
#     # Appel au service métier
#     instrument = instrument_service.create_instrument(dto)
    
#     return instrument

InstrumentMutation = InstrumentMutation
InstrumentQuery = InstrumentQuery