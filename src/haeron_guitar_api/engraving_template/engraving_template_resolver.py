import strawberry
from typing import Optional
from uuid import UUID

from authUser.permission.permission import HasRole, IsAuthenticated

from .egraving_template_service import EngravingTemplateService
from .engraving_template_input import EngravingTemplateCreateInput, EngravingTemplateUpdateInput
from haeron_guitar_api.types.types import EngravingTemplateGQLType


@strawberry.type
class EngravingTemplateDeleteError:
    uuid: str
    error: str


@strawberry.type
class EngravingTemplateBulkDeleteResult:
    deleted: list[str]
    errors: list[EngravingTemplateDeleteError]


@strawberry.type
class EngravingTemplateQuery:

    @strawberry.field(permission_classes=[IsAuthenticated])
    def engraving_template(self, uuid: UUID) -> EngravingTemplateGQLType:
        template = EngravingTemplateService.get(uuid)
        return template

    @strawberry.field(permission_classes=[IsAuthenticated])
    def engraving_templates(
        self,
        mark_type: Optional[str] = None,
        part_model_uuid: Optional[UUID] = None,
    ) -> list[EngravingTemplateGQLType]:
        templates = EngravingTemplateService.list(mark_type=mark_type, part_model_uuid=part_model_uuid)
        return [t for t in templates]


@strawberry.type
class EngravingTemplateMutation:

    @strawberry.mutation(permission_classes=[IsAuthenticated, HasRole("superadmin")])
    def create_engraving_template(self, input: EngravingTemplateCreateInput) -> EngravingTemplateGQLType:
        print("je suis dnas la fonction")
        template = EngravingTemplateService.create(
            name=input.name,
            mark_type=input.mark_type,
            location=input.location,
            lightburn_project_path=input.lightburn_project_path,
            variable_columns=input.variable_columns,
            part_model_uuid=input.part_model_uuid,
        )
        return template

    @strawberry.mutation(permission_classes=[IsAuthenticated, HasRole("superadmin")])
    def update_engraving_template(self, input: EngravingTemplateUpdateInput) -> EngravingTemplateGQLType:
        template = EngravingTemplateService.update(
            uuid=input.uuid,
            name=input.name,
            mark_type=input.mark_type,
            location=input.location,
            lightburn_project_path=input.lightburn_project_path,
            variable_columns=input.variable_columns,
            part_model_uuid=input.part_model_uuid,
            clear_part_model=input.clear_part_model,
        )
        return template

    @strawberry.mutation(permission_classes=[IsAuthenticated, HasRole("superadmin")])
    def delete_engraving_template(self, uuid: UUID) -> bool:
        EngravingTemplateService.delete(uuid)
        return True

    @strawberry.mutation(permission_classes=[IsAuthenticated, HasRole("superadmin")])
    def delete_engraving_templates(self, uuids: list[UUID]) -> EngravingTemplateBulkDeleteResult:
        result = EngravingTemplateService.delete_many(uuids)
        return EngravingTemplateBulkDeleteResult(
            deleted=result["deleted"],
            errors=[EngravingTemplateDeleteError(uuid=e["uuid"], error=e["error"]) for e in result["errors"]],
        )

EngravingTemplateMutation = EngravingTemplateMutation
EngravingTemplateQuery = EngravingTemplateQuery