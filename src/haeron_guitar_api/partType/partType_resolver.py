import strawberry
from uuid import UUID
from typing import List, Optional

from ..models import PartType

from .partType_dto import CreatePartTypeDTO
from .partType_input import CreatePartTypeInput, PartTypeFilterInput
from .partType_service import PartTypeService
from .partType_filter import PartTypeFilterSet
from ..types import PartTypeGQLType
@strawberry.type
class PartTypeQuery:
    @strawberry.field
    def get_part_type(self, uuid: UUID) -> PartTypeGQLType:
        instrument_type = PartType.objects.get(pk=uuid)
        return instrument_type
    
    @strawberry.field
    def part_types(self, filters: Optional[PartTypeFilterInput] = None):
        qs = PartType.objects.all()
        if filters:
            filter_dict = {k: v for k, v in vars(filters).items() if v is not None}
            qs = PartTypeFilterSet(filter_dict, queryset=qs).qs
        return qs
    
    @strawberry.field
    def get_all_part_type(self) -> List[PartTypeGQLType]:
        return PartType.objects.all()

@strawberry.type
class PartTypeMutation:
    @strawberry.mutation
    def create_part_type(self, input: CreatePartTypeInput) -> PartTypeGQLType:
        dto = CreatePartTypeDTO(
            input.name,
            input.code,
            input.intrument_types
        )
        instrument_type = PartTypeService.create(dto)
        return instrument_type
    

    # TODO - make some mutation to delete with name  or code  because they're unique see models
    @strawberry.mutation
    def delete_part_type(self, uuid: strawberry.ID) -> bool:
        """
        Supprime un InstrumentType. Retourne True si la suppression a réussi, False sinon.
        """
        qs = PartType.objects.filter(uuid=uuid)
        if qs.exists():
            qs.delete()
            return True
        return False
   
PartTypeQuery = PartTypeQuery
PartTypeMutation = PartTypeMutation