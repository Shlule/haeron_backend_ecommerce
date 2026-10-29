"""GraphQL CRUD of the back-office, generated from backoffice/registry.py.

For every registered model `X` :
- type `BoX` (all fields, relations as nested types, `label` = str(instance))
- inputs `BoXCreateInput` and `BoXUpdateInput` (relations given by primary key)
- queries `backoffice { xList(offset, limit, search) { totalCount results }  x(pk) }`
- mutations `backoffice { createX(data)  updateX(data)  deleteX(pk) }` (not for read only tables)

`backoffice { resources }` describes the tables and their fields for the back-office forms.
Everything under `backoffice` requires one of the staff roles (see BackofficeAccess / BackofficeWrite).
"""

import datetime
import decimal
import sys
import uuid
from typing import Annotated, Optional

import strawberry
import strawberry_django
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import ProtectedError, Q
from strawberry.scalars import JSON

from authUser.permission.permission import HasRole, IsAuthenticated

from .registry import COMMON_EXCLUDE, REGISTERED, RESOURCES

READ_ROLES = ("superadmin", "admin", "rnd", "production_manager")
WRITE_ROLES = ("superadmin", "admin", "rnd")

_module = sys.modules[__name__]


def _camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)


def _lower_first(name: str) -> str:
    return name[0].lower() + name[1:]


def _snake(name: str) -> str:
    """PartModel -> part_model (strawberry turns it back into partModel)."""
    return "".join(f"_{char.lower()}" if char.isupper() else char for char in name).lstrip("_")


def _fields(resource):
    """Model fields exposed for this resource : concrete fields and many to many, minus the excluded ones."""
    excluded = set(COMMON_EXCLUDE) | set(resource.exclude)
    result = []
    for field in resource.model._meta.get_fields():
        if field.auto_created and not field.concrete:
            continue  # reverse relations
        if field.name in excluded:
            continue
        if field.is_relation and field.related_model not in REGISTERED:
            continue  # relation to a table that is not in the back-office (users...)
        result.append(field)
    return result


def _scalar_type(field):
    if isinstance(field, (models.BooleanField,)):
        return bool
    if isinstance(field, (models.IntegerField, models.AutoField, models.BigAutoField)):
        return int
    if isinstance(field, models.DecimalField):
        return decimal.Decimal
    if isinstance(field, models.FloatField):
        return float
    if isinstance(field, models.DateTimeField):
        return datetime.datetime
    if isinstance(field, models.DateField):
        return datetime.date
    if isinstance(field, models.UUIDField):
        return uuid.UUID
    if isinstance(field, models.JSONField):
        return JSON
    return str


def _kind(field):
    """Kind of field for the back-office forms."""
    if field.many_to_many:
        return "many"
    if field.is_relation:
        return "relation"
    if field.choices:
        return "choice"
    return {
        bool: "boolean",
        int: "integer",
        decimal.Decimal: "decimal",
        float: "decimal",
        datetime.datetime: "datetime",
        datetime.date: "date",
        uuid.UUID: "text",
        JSON: "json",
    }.get(_scalar_type(field), "textarea" if isinstance(field, models.TextField) else "text")


def _editable(field):
    return field.editable and not field.primary_key and not getattr(field, "auto_now", False) and not getattr(field, "auto_now_add", False)


def _required(field):
    if field.many_to_many:
        return False
    return not (field.null or field.blank or field.has_default())


def _label(instance, depth=0) -> str:
    """Readable name of a row : its __str__, else a name-like field, else the first linked row."""
    if type(instance).__str__ is not models.Model.__str__:
        return str(instance)
    for candidate in ("name", "code", "key", "serial_number", "title"):
        value = getattr(instance, candidate, None)
        if value:
            return str(value)
    if depth == 0:
        for field in instance._meta.concrete_fields:
            if field.is_relation and getattr(instance, field.attname, None):
                return _label(getattr(instance, field.name), depth + 1)
    resource = REGISTERED.get(type(instance))
    return f"{resource.label if resource else type(instance).__name__} {str(instance.pk)[:8]}"


def _build_type(resource):
    """`BoX` : the GraphQL type of a table."""
    pk = resource.model._meta.pk
    annotations = {}
    names = [pk.name]
    for field in _fields(resource):
        if field.primary_key:
            continue
        names.append(field.name)
        if field.is_relation:
            target = f"Bo{field.related_model.__name__}"
            lazy = Annotated[target, strawberry.lazy(__name__)]
            annotations[field.name] = list[lazy] if field.many_to_many else (Optional[lazy] if field.null else lazy)
        else:
            annotations[field.name] = strawberry.auto
    annotations[pk.name] = strawberry.auto

    def label(self) -> str:
        return _label(self)

    namespace = {"__annotations__": annotations, "__module__": __name__, "label": strawberry.field(resolver=label)}
    cls = type(f"Bo{resource.name}", (), namespace)
    return strawberry_django.type(resource.model, fields=names)(cls)


def _build_input(resource, update: bool):
    """`BoXCreateInput` / `BoXUpdateInput` : relations are given by primary key."""
    annotations = {}
    defaults = {}
    pk = resource.model._meta.pk
    if update:
        annotations["pk"] = strawberry.ID
    for field in _fields(resource):
        if not _editable(field):
            continue
        if field.many_to_many:
            python_type = list[strawberry.ID]
        elif field.is_relation:
            python_type = strawberry.ID
        else:
            python_type = _scalar_type(field)
        if update or not _required(field):
            annotations[field.name] = Optional[python_type]
            defaults[field.name] = strawberry.UNSET
        else:
            annotations[field.name] = python_type
    suffix = "UpdateInput" if update else "CreateInput"
    cls = type(f"Bo{resource.name}{suffix}", (), {"__annotations__": annotations, "__module__": __name__, **defaults})
    return strawberry.input(cls)


def _build_page(resource, node):
    cls = type(
        f"Bo{resource.name}Page",
        (),
        {"__annotations__": {"total_count": int, "results": list[node]}, "__module__": __name__},
    )
    return strawberry.type(cls)


def _error_message(error):
    if isinstance(error, ValidationError):
        if hasattr(error, "message_dict"):
            return " ".join(f"{field} : {', '.join(messages)}" for field, messages in error.message_dict.items())
        return " ".join(error.messages)
    if isinstance(error, ProtectedError):
        return "Suppression impossible : d'autres données utilisent encore cette ligne."
    return str(error)


def _save(resource, instance, data, created):
    """Writes the input on the instance, validates and saves it (relations by primary key)."""
    many = {}
    for field in _fields(resource):
        if not _editable(field):
            continue
        value = getattr(data, field.name, strawberry.UNSET)
        if value is strawberry.UNSET:
            continue
        if field.many_to_many:
            many[field] = value or []
        elif field.is_relation:
            setattr(instance, field.attname, value)
        else:
            setattr(instance, field.name, value)
    try:
        with transaction.atomic():
            instance.full_clean()
            instance.save()
            for field, ids in many.items():
                getattr(instance, field.name).set(field.related_model._default_manager.filter(pk__in=ids))
            if created and resource.after_create:
                resource.after_create(instance)
    except (ValidationError, ProtectedError, ValueError) as error:
        raise Exception(_error_message(error)) from error
    return instance


def _search(resource, queryset, text):
    text = (text or "").strip()
    if not text:
        return queryset
    query = Q()
    for field in _fields(resource):
        if isinstance(field, (models.CharField, models.TextField)) and not field.choices:
            query |= Q(**{f"{field.name}__icontains": text})
    return queryset.filter(query) if query else queryset


def _ordering(resource):
    meta = resource.model._meta
    if meta.ordering:
        return meta.ordering
    names = {field.name for field in _fields(resource)}
    for candidate in ("name", "code", "key", "-created_at"):
        if candidate.lstrip("-") in names:
            return [candidate]
    return ["pk"]


def _resource_description(resource):
    fields = []
    for field in _fields(resource):
        description = {
            "name": _camel(field.name),
            "label": str(field.verbose_name).capitalize(),
            "kind": "id" if field.primary_key else _kind(field),
            "required": _required(field),
            "editable": _editable(field),
            "helpText": str(field.help_text or ""),
        }
        if field.choices:
            description["choices"] = [{"value": value, "label": str(label)} for value, label in field.choices]
        if field.is_relation:
            description["relation"] = field.related_model.__name__
        if getattr(field, "max_length", None):
            description["maxLength"] = field.max_length
        fields.append(description)
    return {
        "name": resource.name,
        "label": resource.label,
        "group": resource.group,
        "readonly": resource.readonly,
        "pk": _camel(resource.model._meta.pk.name),
        "list": _lower_first(resource.name) + "List",
        "get": _lower_first(resource.name),
        "create": f"create{resource.name}",
        "update": f"update{resource.name}",
        "delete": f"delete{resource.name}",
        "fields": fields,
    }


# ---------------------------------------------------------------------------
# generation

_query_fields = {}
_mutation_fields = {}

for _resource in RESOURCES:
    _node = _build_type(_resource)
    setattr(_module, _node.__name__, _node)
    _page = _build_page(_resource, _node)

    def _make_list(resource=_resource, node=_node, page=_page):
        def resolve(offset: int = 0, limit: int = 50, search: Optional[str] = None) -> page:
            queryset = _search(resource, resource.model._default_manager.all(), search).order_by(*_ordering(resource))
            limit = max(1, min(limit, 200))
            return page(total_count=queryset.count(), results=list(queryset[offset : offset + limit]))

        return resolve

    def _make_get(resource=_resource, node=_node):
        def resolve(pk: strawberry.ID) -> Optional[node]:
            return resource.model._default_manager.filter(pk=pk).first()

        return resolve

    _name = _snake(_resource.name)
    _query_fields[f"{_name}_list"] = strawberry.field(resolver=_make_list())
    _query_fields[_name] = strawberry.field(resolver=_make_get())

    if _resource.readonly:
        continue

    _create_input = _build_input(_resource, update=False)
    _update_input = _build_input(_resource, update=True)

    def _make_create(resource=_resource, node=_node, input_type=_create_input):
        def resolve(data: input_type) -> node:
            return _save(resource, resource.model(), data, created=True)

        return resolve

    def _make_update(resource=_resource, node=_node, input_type=_update_input):
        def resolve(data: input_type) -> node:
            instance = resource.model._default_manager.filter(pk=data.pk).first()
            if instance is None:
                raise Exception(f"{resource.label} : ligne introuvable")
            return _save(resource, instance, data, created=False)

        return resolve

    def _make_delete(resource=_resource):
        def resolve(pk: strawberry.ID) -> bool:
            instance = resource.model._default_manager.filter(pk=pk).first()
            if instance is None:
                return False
            try:
                instance.delete()
            except ProtectedError as error:
                raise Exception(_error_message(error)) from error
            return True

        return resolve

    _mutation_fields[f"create_{_name}"] = strawberry.mutation(resolver=_make_create())
    _mutation_fields[f"update_{_name}"] = strawberry.mutation(resolver=_make_update())
    _mutation_fields[f"delete_{_name}"] = strawberry.mutation(resolver=_make_delete())


def _resources() -> JSON:
    return [_resource_description(resource) for resource in RESOURCES]


_query_fields["resources"] = strawberry.field(resolver=_resources)

BackofficeQueries = strawberry.type(type("BackofficeQueries", (), {"__module__": __name__, **_query_fields}))
BackofficeMutations = strawberry.type(type("BackofficeMutations", (), {"__module__": __name__, **_mutation_fields}))


@strawberry.type
class BackofficeQuery:
    @strawberry.field(permission_classes=[IsAuthenticated, HasRole(*READ_ROLES)])
    def backoffice(self) -> BackofficeQueries:
        return BackofficeQueries()


@strawberry.type
class BackofficeMutation:
    @strawberry.field(permission_classes=[IsAuthenticated, HasRole(*WRITE_ROLES)])
    def backoffice(self) -> BackofficeMutations:
        return BackofficeMutations()
