import strawberry
from uuid import UUID
from typing import List

from ..models import Instrument

from .instrument_input import CreateInstrumentInput
from .instrument_dto import CreateInstrumentDTO
from .Instrument_service import create_instrument
from ..types.types import InstrumentGQLType
from authUser.permission.permission import HasRole, IsAuthenticated


@strawberry.type
class InstrumentQuery:
    @strawberry.field(permission_classes=[IsAuthenticated, HasRole("superadmin", "admin", "production_manager"  )])
    def get_instrument(self, uuid: UUID) -> InstrumentGQLType:
        intrument = Instrument.objects.get(pk=uuid)
        return intrument

    @strawberry.field(permission_classes=[IsAuthenticated, HasRole("superadmin", "admin", "production_manager"  )])
    def get_all_instruments(self) -> List[InstrumentGQLType]:
        return Instrument.objects.all()


@strawberry.type
class InstrumentMutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated, HasRole("superadmin", "admin", "production_manager"  )])
    def create_instrument(self, input: CreateInstrumentInput) -> InstrumentGQLType:
        dto = CreateInstrumentDTO(input.instrument_type_id, input.owner_id, input.master_part_id, input.parts_id)
        instrument = create_instrument(dto)
        return instrument



InstrumentMutation = InstrumentMutation
InstrumentQuery = InstrumentQuery
