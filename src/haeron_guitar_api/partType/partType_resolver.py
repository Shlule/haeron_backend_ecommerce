import strawberry
from uuid import UUID
from typing import List, Optional

from ..models import PartType

from .partType_dto import CreatePartTypeDTO
from .partType_input import CreatePartTypeInput, PartTypeFilterInput
from .partType_service import PartTypeService
from .partType_filter import PartTypeFilterSet
from ..types.types import PartTypeGQLType


@strawberry.type
class PartTypeQuery:
    @strawberry.field
    def get_part_type(self, uuid: UUID) -> PartTypeGQLType:
        instrument_type = PartType.objects.get(pk=uuid)
        return instrument_type

    # TODO faire focntionne les filter set avec django filters
    @strawberry.field
    def part_types(self, filters: Optional[PartTypeFilterInput] = None) -> List[PartTypeGQLType]:
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
        dto = CreatePartTypeDTO(name=input.name, code=input.code, instrument_Types=input.intrument_types or [])
        part_type = PartTypeService.create(dto)

        if input.intrument_types:
            PartTypeService.add_instruments_types(part_type.uuid, dto.instrument_Types)

        return part_type

    @strawberry.mutation
    def add_part_type_instrument_type_connec(part_type_id: UUID, instrument_type_ids: List[UUID]) -> bool:
        result = PartTypeService.add_instruments_types(part_type_id, instrument_type_ids)
        return result

    @strawberry.mutation
    def rm_part_type_instrument_type_connec(part_type_id: UUID, instrument_type_ids: List[UUID]) -> bool:
        result = PartTypeService.remove_instruments_types(part_type_id, instrument_type_ids)
        return result

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
