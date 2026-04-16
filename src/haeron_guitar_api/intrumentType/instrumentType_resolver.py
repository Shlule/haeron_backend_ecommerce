import strawberry
from uuid import UUID
from typing import List, Optional

from ..models import InstrumentType

from .instrumentType_dto import CreateInstrumentTypeDTO
from .instrumentType_input import CreateInstrumentTypeInput, InstrumentTypeFilterInput
from .instrumentType_filter import InstrumentTypeFilterSet
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

    @strawberry.field
    def instrument_types(self, filters: Optional[InstrumentTypeFilterInput] = None) -> List[InstrumentTypeGQLType]:
        qs = InstrumentType.objects.all()
        if filters:
            filter_dict = {k: v for k, v in filters.__dict__.items() if v is not None}
            qs = InstrumentTypeFilterSet(filter_dict, queryset=qs).qs
        return qs


@strawberry.type
class InstrumentTypeMutation:
    @strawberry.mutation()
    def create_instrument_type(self, input: CreateInstrumentTypeInput) -> InstrumentTypeGQLType:
        dto = CreateInstrumentTypeDTO(name=input.name, code=input.code, part_types=input.part_types or [])
        instrument_type = InstrumentTypeService.create(dto)

        if input.part_types:
            InstrumentTypeService.add_parts_types(instrument_type.uuid, dto.part_types)

        return instrument_type

    @strawberry.mutation
    def add_instrument_type_part_type_connec(instrument_type_id: UUID, part_types_ids: List[UUID]) -> bool:
        result = InstrumentTypeService.add_parts_types(instrument_type_id, part_types_ids)
        return result

    @strawberry.mutation
    def rm_instrument_type_part_type_connec(instrument_type_id: UUID, part_types_ids: List[UUID]) -> bool:
        result = InstrumentTypeService.remove_parts_types(instrument_type_id, part_types_ids)
        return result

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
