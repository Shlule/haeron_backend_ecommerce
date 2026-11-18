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

from ..finance.finance_service import FinanceService
from ..order.order_service import OrderService
from ..production.part_model_builder import PartModelBuilder
from ..production.production_service import EVENT_TYPES, ProductionService
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
            # an emptied field arrives as null : a column refusing null gets back its default value ("" for a text)
            if value is None and not field.null:
                if field.has_default():
                    value = field.get_default()
                elif isinstance(field, (models.CharField, models.TextField)):
                    value = ""
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


# orders : list and technical sheet of each item (the generic tables only show the raw snapshot)
def _orders(offset: int = 0, limit: int = 50, status: Optional[str] = None, search: Optional[str] = None) -> JSON:
    return OrderService.list(offset, limit, status, search)


def _order_sheet(order_id: uuid.UUID) -> Optional[JSON]:
    return OrderService.detail(order_id)


def _set_order_status(order_id: uuid.UUID, status: str) -> JSON:
    try:
        return OrderService.set_status(order_id, status)
    except ValidationError as error:
        raise Exception(_error_message(error)) from error


_query_fields["orders"] = strawberry.field(resolver=_orders)
# "order" is already the generic read of the Order table
_query_fields["order_sheet"] = strawberry.field(resolver=_order_sheet)
_mutation_fields["set_order_status"] = strawberry.mutation(resolver=_set_order_status)
# money in and out (payments, refunds, Stripe fees) : managers only
FINANCE_ROLES = ("superadmin", "admin")


def _finances(date_from: Optional[datetime.date] = None, date_to: Optional[datetime.date] = None) -> JSON:
    return FinanceService.summary(date_from, date_to)


_query_fields["finances"] = strawberry.field(
    resolver=_finances, permission_classes=[IsAuthenticated, HasRole(*FINANCE_ROLES)]
)

# workshop : instruments and parts made, their history (see production/production_service.py)
@strawberry.input
class BoOptionPriceInput:
    """Supplement of a chosen value for this part only (the catalogue price stays as it is)."""

    option_id: uuid.UUID
    price_delta: decimal.Decimal


@strawberry.input
class BoPartLineInput:
    part_model_id: Optional[uuid.UUID] = None
    option_ids: list[uuid.UUID] = strawberry.field(default_factory=list)
    option_prices: list[BoOptionPriceInput] = strawberry.field(default_factory=list)
    description: str = ""
    existing_part_id: Optional[uuid.UUID] = None


@strawberry.input
class BoBuildInstrumentInput:
    instrument_model_id: uuid.UUID
    factory_id: uuid.UUID
    parts: list[BoPartLineInput]
    master_index: int = 0
    description: str = ""
    owner_email: Optional[str] = None
    order_id: Optional[uuid.UUID] = None
    order_item_index: Optional[int] = None
    status: Optional[str] = None  # sold when made for an order, else in stock


@strawberry.input
class BoBuildPartInput:
    part_model_id: uuid.UUID
    factory_id: uuid.UUID
    instrument_type_id: uuid.UUID
    option_ids: list[uuid.UUID] = strawberry.field(default_factory=list)
    option_prices: list[BoOptionPriceInput] = strawberry.field(default_factory=list)
    description: str = ""
    owner_email: Optional[str] = None
    is_master: bool = False
    status: Optional[str] = None


@strawberry.input
class BoHistoryEventInput:
    target: str  # "instrument" or "part"
    target_id: uuid.UUID
    event_type: str
    title: str = ""
    description: str = ""


def _staff_user(info):
    return info.context["request"].user


def _production(call):
    try:
        return call()
    except ValidationError as error:
        raise Exception(_error_message(error)) from error


def _production_form() -> JSON:
    return ProductionService.form_data()


def _history_event_types() -> JSON:
    return [{"value": value, "label": label} for value, label in EVENT_TYPES]


def _instruments(
    offset: int = 0, limit: int = 50, search: Optional[str] = None, status: Optional[str] = None
) -> JSON:
    return ProductionService.instruments(offset, limit, search, status)


def _instrument_sheet(instrument_id: uuid.UUID) -> Optional[JSON]:
    return ProductionService.instrument_sheet(instrument_id)


def _produced_parts(
    offset: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    free_only: bool = False,
    status: Optional[str] = None,
) -> JSON:
    return ProductionService.parts(offset, limit, search, free_only, status)


def _part_sheet(part_id: uuid.UUID) -> Optional[JSON]:
    return ProductionService.part_sheet(part_id)


def _build_instrument(info: strawberry.Info, data: BoBuildInstrumentInput) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: ProductionService.build_instrument(payload, _staff_user(info)))


def _build_part(info: strawberry.Info, data: BoBuildPartInput) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: ProductionService.build_part(payload, _staff_user(info)))


def _update_instrument_info(
    info: strawberry.Info, instrument_id: uuid.UUID, description: Optional[str] = None, owner_email: Optional[str] = None
) -> JSON:
    return _production(
        lambda: ProductionService.update_instrument(instrument_id, description, owner_email, _staff_user(info))
    )


def _update_part_info(info: strawberry.Info, part_id: uuid.UUID, description: str) -> JSON:
    return _production(lambda: ProductionService.update_part(part_id, description, _staff_user(info)))


def _create_part_batch(part_model_id: uuid.UUID, name: str, code: str) -> JSON:
    return _production(lambda: ProductionService.create_batch(part_model_id, name, code))


def _add_history_event(info: strawberry.Info, data: BoHistoryEventInput) -> JSON:
    return _production(
        lambda: ProductionService.add_event(
            data.target, data.target_id, data.event_type, data.title, data.description, _staff_user(info)
        )
    )


def _set_production_status(
    info: strawberry.Info, target: str, target_id: uuid.UUID, status: str, note: str = ""
) -> JSON:
    return _production(lambda: ProductionService.set_status(target, target_id, status, note, _staff_user(info)))


def _delete_history_event(event_id: uuid.UUID) -> bool:
    return _production(lambda: ProductionService.delete_event(event_id))


_query_fields["production_form"] = strawberry.field(resolver=_production_form)
_query_fields["history_event_types"] = strawberry.field(resolver=_history_event_types)
_query_fields["instruments"] = strawberry.field(resolver=_instruments)
_query_fields["instrument_sheet"] = strawberry.field(resolver=_instrument_sheet)
_query_fields["produced_parts"] = strawberry.field(resolver=_produced_parts)
_query_fields["part_sheet"] = strawberry.field(resolver=_part_sheet)
# making parts gives serial numbers and fixes their options for good : managers only
BUILD_ROLES = ("superadmin", "admin")
_build_permissions = [IsAuthenticated, HasRole(*BUILD_ROLES)]


def _can_build_parts(info: strawberry.Info) -> bool:
    user = _staff_user(info)
    return bool(user.is_authenticated and user.groups.filter(name__in=BUILD_ROLES).exists())


_query_fields["can_build_parts"] = strawberry.field(resolver=_can_build_parts)
_mutation_fields["build_instrument"] = strawberry.mutation(resolver=_build_instrument, permission_classes=_build_permissions)
_mutation_fields["build_part"] = strawberry.mutation(resolver=_build_part, permission_classes=_build_permissions)
_mutation_fields["update_instrument_info"] = strawberry.mutation(resolver=_update_instrument_info)
_mutation_fields["update_part_info"] = strawberry.mutation(resolver=_update_part_info)
_mutation_fields["create_part_batch"] = strawberry.mutation(resolver=_create_part_batch, permission_classes=_build_permissions)


# new part model of the catalogue with its options and values in one form : managers only, like making parts
@strawberry.input
class BoOptionValueInput:
    code: str
    name: str = ""
    price_delta: decimal.Decimal = decimal.Decimal(0)


@strawberry.input
class BoPartModelOptionGroupInput:
    option_id: Optional[uuid.UUID] = None
    new_option_name: Optional[str] = None
    values: list[BoOptionValueInput] = strawberry.field(default_factory=list)


@strawberry.input
class BoNewPartModelInput:
    name: str
    code: str
    part_type_id: uuid.UUID
    series_id: Optional[uuid.UUID] = None
    price: decimal.Decimal = decimal.Decimal(0)
    status: str = "active"
    options: list[BoPartModelOptionGroupInput] = strawberry.field(default_factory=list)


def _part_model_form() -> JSON:
    return PartModelBuilder.form_data()


def _create_part_model_with_options(data: BoNewPartModelInput) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: PartModelBuilder.create(payload))


_query_fields["part_model_form"] = strawberry.field(resolver=_part_model_form)
_mutation_fields["create_part_model_with_options"] = strawberry.mutation(
    resolver=_create_part_model_with_options, permission_classes=_build_permissions
)
_mutation_fields["add_history_event"] = strawberry.mutation(resolver=_add_history_event)
_mutation_fields["delete_history_event"] = strawberry.mutation(resolver=_delete_history_event)
_mutation_fields["set_production_status"] = strawberry.mutation(resolver=_set_production_status)


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
