import strawberry
from uuid import UUID
from typing import List

from ..models import InstrumentType

from .instrumentType_dto import CreateInstrumentTypeDTO
from .instrumentType_input import CreateInstrumentTypeInput
from .instrumentType_service import InstrumentTypeService
from ..permissions.authenticateJwt import IsAuthenticated
from ..permissions.groupPermission import HasRoleFactory
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
    @strawberry.mutation()
    def create_instrument_type(self, input: CreateInstrumentTypeInput) -> InstrumentTypeGQLType:
        dto = CreateInstrumentTypeDTO(
            input.name,
            input.code,
        )
        instrument_type = InstrumentTypeService.create(dto)
        return instrument_type
    

    # TODO - make some mutation to delete with name  or code  because they're unique see models
    @strawberry.mutation
    def delete_instrument_type(self, uuid: strawberry.ID) -> bool:
        """
        Supprime un InstrumentType. Retourne True si la suppression a réussi, False sinon.
        """
        qs = InstrumentType.objects.filter(uuid=uuid)
        if qs.exists():
            qs.delete()
            return True
        return False
   
InstrumentTypeQuery = InstrumentTypeQuery
InstrumentTypeMutation = InstrumentTypeMutation