from django.db import IntegrityError
from django.db.models import ProtectedError

from haeron_guitar_api.models import EngravingTemplate, PartModel


class EngravingTemplateError(Exception):
    """Erreur métier, destinée à remonter tel quel comme message GraphQL."""


class EngravingTemplateService:

    VALID_MARK_TYPES = {choice[0] for choice in EngravingTemplate._meta.get_field("mark_type").choices}

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @classmethod
    def _validate(cls, *, name, mark_type, location, lightburn_project_path, variable_columns):
        if not name or not name.strip():
            raise EngravingTemplateError("Le nom est obligatoire.")
        if mark_type not in cls.VALID_MARK_TYPES:
            raise EngravingTemplateError(
                f"mark_type invalide : {mark_type!r}. Valeurs possibles : {sorted(cls.VALID_MARK_TYPES)}"
            )
        if not location or not location.strip():
            raise EngravingTemplateError("location est obligatoire.")
        if not lightburn_project_path or not lightburn_project_path.strip():
            raise EngravingTemplateError("lightburn_project_path est obligatoire.")
        if not variable_columns or not all(isinstance(c, str) and c for c in variable_columns):
            raise EngravingTemplateError("variable_columns doit être une liste non vide de noms de colonnes.")

    @staticmethod
    def _resolve_part_model(part_model_uuid) -> PartModel:
        try:
            return PartModel.objects.get(uuid=part_model_uuid)
        except PartModel.DoesNotExist:
            raise EngravingTemplateError(f"PartModel introuvable : {part_model_uuid}")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, *, name, mark_type, location, lightburn_project_path,
               variable_columns, part_model_uuid=None) -> EngravingTemplate:
        cls._validate(
            name=name, mark_type=mark_type, location=location,
            lightburn_project_path=lightburn_project_path, variable_columns=variable_columns,
        )

        part_model = cls._resolve_part_model(part_model_uuid) if part_model_uuid else None

        try:
            return EngravingTemplate.objects.create(
                name=name, mark_type=mark_type, location=location,
                lightburn_project_path=lightburn_project_path,
                variable_columns=list(variable_columns), part_model=part_model,
            )
        except IntegrityError:
            raise EngravingTemplateError(f"Un template nommé {name!r} existe déjà.")

    @classmethod
    def update(cls, *, uuid, name=None, mark_type=None, location=None,
               lightburn_project_path=None, variable_columns=None,
               part_model_uuid=None, clear_part_model=False) -> EngravingTemplate:
        template = cls.get(uuid)

        new_name = name if name is not None else template.name
        new_mark_type = mark_type if mark_type is not None else template.mark_type
        new_location = location if location is not None else template.location
        new_path = lightburn_project_path if lightburn_project_path is not None else template.lightburn_project_path
        new_columns = variable_columns if variable_columns is not None else template.variable_columns

        cls._validate(
            name=new_name, mark_type=new_mark_type, location=new_location,
            lightburn_project_path=new_path, variable_columns=new_columns,
        )

        if clear_part_model:
            template.part_model = None
        elif part_model_uuid is not None:
            template.part_model = cls._resolve_part_model(part_model_uuid)

        template.name = new_name
        template.mark_type = new_mark_type
        template.location = new_location
        template.lightburn_project_path = new_path
        template.variable_columns = list(new_columns)

        try:
            template.save()
        except IntegrityError:
            raise EngravingTemplateError(f"Un template nommé {new_name!r} existe déjà.")

        return template

    @classmethod
    def delete(cls, uuid) -> None:
        template = cls.get(uuid)
        try:
            template.delete()
        except ProtectedError:
            n = template.marks.count()
            raise EngravingTemplateError(
                f"Suppression impossible : {n} marque(s) de gravure référence(nt) encore ce template."
            )

    @classmethod
    def delete_many(cls, uuids: list) -> dict:
        """
        Suppression best-effort : un template protégé (référencé par des marques)
        n'empêche pas la suppression des autres. Le détail de chaque échec est
        retourné pour affichage côté client.
        """
        deleted, errors = [], []
        for u in uuids:
            try:
                cls.delete(u)
                deleted.append(str(u))
            except EngravingTemplateError as e:
                errors.append({"uuid": str(u), "error": str(e)})
        return {"deleted": deleted, "errors": errors}

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    @staticmethod
    def get(uuid) -> EngravingTemplate:
        try:
            return EngravingTemplate.objects.select_related("part_model", "part_model__part_type").get(uuid=uuid)
        except EngravingTemplate.DoesNotExist:
            raise EngravingTemplateError(f"Template introuvable : {uuid}")

    @staticmethod
    def list(*, mark_type: str = None, part_model_uuid=None):
        qs = EngravingTemplate.objects.select_related("part_model", "part_model__part_type").order_by("name")
        if mark_type:
            qs = qs.filter(mark_type=mark_type)
        if part_model_uuid:
            qs = qs.filter(part_model__uuid=part_model_uuid)
        return qs