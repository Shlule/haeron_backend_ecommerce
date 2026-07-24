import strawberry
from uuid import UUID
from typing import List

from ..models import Part
from ..types.types import PartGQLType
from .part_input import CreatePartInput, UpdatePartInput
from .part_dto import CreatePartDTO, UpdatePartDTO
from .part_service import PartService


@strawberry.type
class PartQuery:
    @strawberry.field
    def get_part(self, uuid: UUID) -> PartGQLType:
        return Part.objects.get(uuid)

    @strawberry.field
    def get_all_part(self) -> List[PartGQLType]:
        return Part.objects.all()


@strawberry.type
class PartMutation:
    @strawberry.mutation
    def create_part(self, input: CreatePartInput) -> PartGQLType:
        dto = CreatePartDTO(
            factory_id=input.factory_id,
            instrument_type_id=input.instrument_type_id,
            part_model_id=input.part_model_id,
            owner_id=input.owner_id,
            is_master=input.is_master,
        )
        return PartService.create(dto)

    @strawberry.mutation
    def update_part(self, uuid: UUID, input: UpdatePartInput) -> PartGQLType:
        part = Part.objects.get(uuid=uuid)
        dto = UpdatePartDTO(
            serial_number=input.serial_number,
            part_model_id=input.part_model_id,
            owner_id=input.owner_id,
            is_master=input.is_master,
        )

        return PartService.update(part, dto)

    def delete_part(delf, uuid: UUID) -> bool:
        Part.objects.get(pk=uuid).delete()


PartQuery = PartQuery
PartMutation = PartMutation
