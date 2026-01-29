import strawberry
from uuid import UUID
from typing import List

from ..models import Option
from .option_dto import CreateOptionDTO
from .option_input import CreateOptionInput
from .option_service import OptionService

from ..types import OptionGQLType

@strawberry.type
class OptionQuery:
    @strawberry.field
    def options(self, uuid: UUID) -> OptionGQLType:
        option = Option.objects.get(pk=uuid) 
        return option
    

@strawberry.type
class OptionMutation: 
    @strawberry.mutation
    def create_option(self, input: CreateOptionInput) -> OptionGQLType:
        dto = CreateOptionDTO(
            input.name,
            input.description,
        )
        option = OptionService.create(dto)
        return option
    
    
    # TODO - make some mutation to delete with name  or code  because they're unique see models
    @strawberry.mutation
    def delete_instrument_type(self, uuid: strawberry.ID) -> bool:
        """
        Supprime un InstrumentType. Retourne True si la suppression a réussi, False sinon.
        """
        qs = Option.objects.filter(uuid=uuid)
        if qs.exists():
            qs.delete()
            return True
        return False
    
OptionQuery = OptionQuery
OptionMutation = OptionMutation