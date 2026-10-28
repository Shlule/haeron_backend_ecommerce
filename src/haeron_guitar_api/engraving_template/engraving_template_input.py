import strawberry
from typing import Optional
from uuid import UUID


@strawberry.input
class EngravingTemplateCreateInput:
    name: str
    mark_type: str
    location: str
    lightburn_project_path: str
    variable_columns: list[str]
    part_model_uuid: Optional[strawberry.ID] = None


@strawberry.input
class EngravingTemplateUpdateInput:
    uuid: UUID
    # tous les champs sont optionnels : seuls ceux fournis (non None) sont modifiés
    name: Optional[str] = None
    mark_type: Optional[str] = None
    location: Optional[str] = None
    lightburn_project_path: Optional[str] = None
    variable_columns: Optional[list[str]] = None
    part_model_uuid: Optional[strawberry.ID] = None
    # part_model_uuid=None est ambigu ("pas fourni" vs "je veux enlever le lien"),
    # donc un flag explicite pour le cas où on veut vraiment retirer le part_model
    clear_part_model: bool = False