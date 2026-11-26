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
from django.db.models import Prefetch, ProtectedError, Q
from strawberry.scalars import JSON

from authUser.permission.permission import HasRole, IsAuthenticated

from ..finance.finance_service import FinanceService
from ..order.order_service import OrderService
from ..payments.payment_service import PaymentService
from ..production.hidden_mark_service import HiddenMarkService
from ..partners.partner_service import PartnerService
from ..purchasing.purchasing_service import PurchasingService, StockService
from ..production.part_model_builder import PartModelBuilder
from ..production.piece_product_builder import PieceProductBuilder
from ..production.product_catalogue import ProductCatalogue
from ..production.catalogue_admin import CatalogueAdmin
from ..production.product_editor import ProductEditor
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


def _many_resolver(name, target):
    # reads the rows prefetched by _with_relations (a strawberry_django relation would query again)
    def resolve(self) -> list[target]:
        return list(getattr(self, name).all())

    return strawberry.field(resolver=resolve)


def _build_type(resource):
    """`BoX` : the GraphQL type of a table."""
    pk = resource.model._meta.pk
    annotations = {}
    names = [pk.name]
    many = {}
    for field in _fields(resource):
        if field.primary_key:
            continue
        if field.is_relation:
            target = f"Bo{field.related_model.__name__}"
            lazy = Annotated[target, strawberry.lazy(__name__)]
            if field.many_to_many:
                many[field.name] = _many_resolver(field.name, lazy)
                continue
            names.append(field.name)
            annotations[field.name] = Optional[lazy] if field.null else lazy
        else:
            names.append(field.name)
            annotations[field.name] = strawberry.auto
    annotations[pk.name] = strawberry.auto

    def label(self) -> str:
        return _label(self)

    namespace = {"__annotations__": annotations, "__module__": __name__, "label": strawberry.field(resolver=label), **many}
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


def _with_relations(resource, queryset):
    """Rows with their linked rows read in the same query (foreign keys) or one query per relation (many to many),
    instead of one query per row and per relation. The linked rows keep their own foreign keys too :
    their label (str) often reads them, e.g. a part model shows its part type."""
    def own_joins(model):
        return [sub.name for sub in model._meta.concrete_fields if sub.is_relation]

    joins, many = [], []
    for field in _fields(resource):
        if field.many_to_many:
            target = field.related_model
            many.append(Prefetch(field.name, queryset=target._default_manager.select_related(*own_joins(target))))
        elif field.is_relation:
            joins.append(field.name)
            joins.extend(f"{field.name}__{name}" for name in own_joins(field.related_model))
    return queryset.select_related(*joins).prefetch_related(*many)


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
        # the model's own default (a switch on by default, a quantity...) prefills the creation form
        if field.has_default() and not callable(field.default) and isinstance(field.default, (bool, int, float, str)):
            description["default"] = field.default
        elif isinstance(field, models.DecimalField) and field.has_default() and not callable(field.default):
            description["default"] = float(field.default)
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
            # count without the joins, then the page with its linked rows
            total = queryset.count()
            queryset = _with_relations(resource, queryset)
            limit = max(1, min(limit, 200))
            return page(total_count=total, results=list(queryset[offset : offset + limit]))

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


def _send_payment_link(order_id: uuid.UUID) -> JSON:
    return _production(lambda: PaymentService.send_payment_link(order_id))


def _ship_order(
    order_id: uuid.UUID, carrier: str, tracking_number: str = "", tracking_url: str = "", notify: bool = True
) -> JSON:
    """Parcel handed to the carrier : order shipped, tracking e-mail to the customer (unless notify is false)."""
    return _production(lambda: OrderService.ship(order_id, carrier, tracking_number, tracking_url, notify))


# money in and out (payments, refunds, Stripe fees) : managers only
FINANCE_ROLES = ("superadmin", "admin")


def _finances(date_from: Optional[datetime.date] = None, date_to: Optional[datetime.date] = None) -> JSON:
    return FinanceService.summary(date_from, date_to)


_query_fields["finances"] = strawberry.field(
    resolver=_finances, permission_classes=[IsAuthenticated, HasRole(*FINANCE_ROLES)]
)


# purchases : supplier invoices (managers only, like the finances) and the stock of the parts bought
# (see purchasing/purchasing_service.py)
_finance_permissions = [IsAuthenticated, HasRole(*FINANCE_ROLES)]


@strawberry.input
class BoPurchaseLineInput:
    unit_price_ht: decimal.Decimal
    label: str = ""
    category: str = "other"
    stock_item_id: Optional[uuid.UUID] = None
    zone: str = ""
    quantity: decimal.Decimal = decimal.Decimal("1")
    vat_rate: decimal.Decimal = decimal.Decimal("20")


@strawberry.input
class BoPurchaseInvoiceInput:
    number: str
    issued_on: datetime.date
    lines: list[BoPurchaseLineInput]
    # an existing supplier, or the name of a new one (created with the invoice)
    supplier_id: Optional[uuid.UUID] = None
    supplier_name: str = ""
    due_on: Optional[datetime.date] = None
    paid_on: Optional[datetime.date] = None
    payment_method: str = ""
    notes: str = ""


@strawberry.input
class BoPurchaseInvoiceUpdateInput:
    number: str
    issued_on: datetime.date
    due_on: Optional[datetime.date] = None
    paid_on: Optional[datetime.date] = None
    payment_method: str = ""
    notes: str = ""


@strawberry.input
class BoStockMoveInput:
    stock_item_id: uuid.UUID
    kind: str
    quantity: decimal.Decimal
    zone: str = "workshop"
    instrument_id: Optional[uuid.UUID] = None
    note: str = ""
    # positive inventory correction : cost of the stock entered without an invoice (empty : average cost)
    unit_cost: Optional[decimal.Decimal] = None


@strawberry.input
class BoStockItemInput:
    name: str
    reference: str = ""
    family: str = ""
    # chosen supplier, or a new one typed by its name (none : both empty)
    supplier_id: Optional[uuid.UUID] = None
    supplier_name: str = ""
    unit: str = "pièce"
    alert_quantity: Optional[decimal.Decimal] = None
    is_active: bool = True
    notes: str = ""
    # new article only : stock already there, entered without an invoice
    initial_quantity: Optional[decimal.Decimal] = None
    initial_zone: str = "workshop"
    initial_unit_cost: Optional[decimal.Decimal] = None


def _purchasing_form() -> JSON:
    return PurchasingService.form_data()


def _purchase_invoices(offset: int = 0, limit: int = 50, search: Optional[str] = None, unpaid_only: bool = False) -> JSON:
    return PurchasingService.invoices(offset, limit, search, unpaid_only)


def _purchase_invoice(invoice_id: uuid.UUID) -> Optional[JSON]:
    return PurchasingService.invoice(invoice_id)


def _create_purchase_invoice(info: strawberry.Info, data: BoPurchaseInvoiceInput) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: PurchasingService.create_invoice(payload, _staff_user(info)))


def _update_purchase_invoice(info: strawberry.Info, invoice_id: uuid.UUID, data: BoPurchaseInvoiceUpdateInput) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: PurchasingService.update_invoice(invoice_id, payload, _staff_user(info)))


def _delete_purchase_invoice(invoice_id: uuid.UUID) -> bool:
    return _production(lambda: PurchasingService.delete_invoice(invoice_id))


def _stock(search: Optional[str] = None, family: Optional[str] = None) -> JSON:
    return StockService.overview(search, family)


def _stock_item_sheet(item_id: uuid.UUID) -> Optional[JSON]:
    return StockService.item_sheet(item_id)


def _instrument_stock_parts(instrument_id: uuid.UUID) -> JSON:
    return StockService.instrument_cost(instrument_id)


def _save_stock_item(info: strawberry.Info, data: BoStockItemInput, item_id: Optional[uuid.UUID] = None) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: StockService.save_item(item_id, payload, _staff_user(info)))


def _move_stock(info: strawberry.Info, data: BoStockMoveInput) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: StockService.move(payload, _staff_user(info)))


_query_fields["purchasing_form"] = strawberry.field(resolver=_purchasing_form)
_query_fields["purchase_invoices"] = strawberry.field(resolver=_purchase_invoices, permission_classes=_finance_permissions)
_query_fields["purchase_invoice"] = strawberry.field(resolver=_purchase_invoice, permission_classes=_finance_permissions)
_query_fields["stock"] = strawberry.field(resolver=_stock)
_query_fields["stock_item_sheet"] = strawberry.field(resolver=_stock_item_sheet)
_query_fields["instrument_stock_parts"] = strawberry.field(resolver=_instrument_stock_parts)
_mutation_fields["create_purchase_invoice"] = strawberry.mutation(
    resolver=_create_purchase_invoice, permission_classes=_finance_permissions
)
_mutation_fields["update_purchase_invoice"] = strawberry.mutation(
    resolver=_update_purchase_invoice, permission_classes=_finance_permissions
)
_mutation_fields["delete_purchase_invoice"] = strawberry.mutation(
    resolver=_delete_purchase_invoice, permission_classes=_finance_permissions
)
_mutation_fields["move_stock"] = strawberry.mutation(resolver=_move_stock)
_mutation_fields["save_stock_item"] = strawberry.mutation(resolver=_save_stock_item)


# business partners : code or link with a discount, commission on what the customers paid, payouts
# (managers only, like the finances ; see partners/partner_service.py)
@strawberry.input
class BoPartnerInput:
    name: str
    code: str
    discount_percent: decimal.Decimal = decimal.Decimal("5")
    commission_percent: decimal.Decimal = decimal.Decimal("10")
    is_active: bool = True
    valid_until: Optional[datetime.date] = None
    email: str = ""
    phone: str = ""
    company: str = ""
    siret: str = ""
    address: str = ""
    notes: str = ""


@strawberry.input
class BoPartnerPayoutInput:
    amount: decimal.Decimal
    paid_on: Optional[datetime.date] = None
    payment_method: str = ""
    note: str = ""


def _partners() -> JSON:
    return PartnerService.list()


def _partner(partner_id: uuid.UUID) -> Optional[JSON]:
    return PartnerService.detail(partner_id)


def _save_partner(data: BoPartnerInput, partner_id: Optional[uuid.UUID] = None) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: PartnerService.save(payload, partner_id))


def _delete_partner(partner_id: uuid.UUID) -> bool:
    return _production(lambda: PartnerService.delete(partner_id))


def _record_partner_payout(info: strawberry.Info, partner_id: uuid.UUID, data: BoPartnerPayoutInput) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: PartnerService.record_payout(partner_id, payload, _staff_user(info)))


def _delete_partner_payout(payout_id: uuid.UUID) -> JSON:
    return _production(lambda: PartnerService.delete_payout(payout_id))


_query_fields["partners"] = strawberry.field(resolver=_partners, permission_classes=_finance_permissions)
_query_fields["partner"] = strawberry.field(resolver=_partner, permission_classes=_finance_permissions)
for _name, _resolver in (
    ("save_partner", _save_partner),
    ("delete_partner", _delete_partner),
    ("record_partner_payout", _record_partner_payout),
    ("delete_partner_payout", _delete_partner_payout),
):
    _mutation_fields[_name] = strawberry.mutation(resolver=_resolver, permission_classes=_finance_permissions)

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
    order_id: Optional[uuid.UUID] = None  # piece sold alone : the order line it is made for
    order_item_index: Optional[int] = None
    status: Optional[str] = None  # sold when made for an order, else in stock


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


def _link_production_order(
    info: strawberry.Info,
    target: str,
    target_id: uuid.UUID,
    order_id: Optional[uuid.UUID] = None,
    order_item_index: Optional[int] = None,
) -> JSON:
    """Gives an instrument or a piece to an order line (sold), or takes it back to stock (no order)."""
    return _production(
        lambda: ProductionService.link_order(target, target_id, order_id, order_item_index, _staff_user(info))
    )


def _delete_history_event(event_id: uuid.UUID) -> bool:
    return _production(lambda: ProductionService.delete_event(event_id))


_query_fields["production_form"] = strawberry.field(resolver=_production_form)
_query_fields["history_event_types"] = strawberry.field(resolver=_history_event_types)
_query_fields["instruments"] = strawberry.field(resolver=_instruments)
_query_fields["instrument_sheet"] = strawberry.field(resolver=_instrument_sheet)
_query_fields["produced_parts"] = strawberry.field(resolver=_produced_parts)
_query_fields["part_sheet"] = strawberry.field(resolver=_part_sheet)


def _check_hidden_mark(part_id: uuid.UUID, code: str) -> JSON:
    return _production(lambda: ProductionService.check_hidden_mark(part_id, code))


_query_fields["check_hidden_mark"] = strawberry.field(resolver=_check_hidden_mark)


def _hidden_mark_to_engrave(info: strawberry.Info, part_id: uuid.UUID) -> JSON:
    return _production(lambda: HiddenMarkService.code_to_engrave(part_id, _staff_user(info)))


def _confirm_hidden_mark(info: strawberry.Info, part_id: uuid.UUID, code: str, location: str = "") -> JSON:
    def confirm():
        # location : where the code was engraved, written by hand (the code does not depend on it)
        HiddenMarkService.confirm_engraving(part_id, code, location, _staff_user(info))
        return ProductionService.part_sheet(part_id)

    return _production(confirm)
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
# the hidden code is shown to the people who make the parts, and only until it is engraved and checked
_mutation_fields["hidden_mark_to_engrave"] = strawberry.mutation(
    resolver=_hidden_mark_to_engrave, permission_classes=_build_permissions
)
_mutation_fields["confirm_hidden_mark"] = strawberry.mutation(
    resolver=_confirm_hidden_mark, permission_classes=_build_permissions
)


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
@strawberry.input
class BoPieceProductInput:
    component_id: uuid.UUID
    name: str
    price: decimal.Decimal = decimal.Decimal(0)
    image: str = ""
    model_3d: str = ""
    visible: bool = True


@strawberry.input
class BoPieceProductsInput:
    instrument_model_id: uuid.UUID
    pieces: list[BoPieceProductInput]


def _piece_product_form() -> JSON:
    return PieceProductBuilder.form_data()


def _create_piece_products(data: BoPieceProductsInput) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: PieceProductBuilder.create(payload))


_query_fields["piece_product_form"] = strawberry.field(resolver=_piece_product_form)
_mutation_fields["create_piece_products"] = strawberry.mutation(resolver=_create_piece_products)
def _add_mutation(name, resolver):
    """A business mutation next to the generic ones (create_product, update_product...) : never under the same name."""
    if name in _mutation_fields:
        raise RuntimeError(f"Back-office mutation {name} already exists")
    _mutation_fields[name] = strawberry.mutation(resolver=resolver)


@strawberry.input
class BoNewProductInput:
    name: str
    price: decimal.Decimal = decimal.Decimal(0)
    image: str = ""
    visible: bool = True


def _catalogue_products() -> JSON:
    return ProductCatalogue.products()


def _create_product(data: BoNewProductInput) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: ProductCatalogue.create(payload))


def _set_product_visible(product_id: uuid.UUID, visible: bool) -> JSON:
    return _production(lambda: ProductCatalogue.set_visible(product_id, visible))


_query_fields["catalogue_products"] = strawberry.field(resolver=_catalogue_products)
_add_mutation("create_shop_product", _create_product)
_add_mutation("set_product_visible", _set_product_visible)
@strawberry.input
class BoProductInput:
    name: str
    price: decimal.Decimal = decimal.Decimal(0)
    instrument_model_id: Optional[uuid.UUID] = None
    image: str = ""
    model_3d: str = ""
    visible: bool = False


@strawberry.input
class BoProductComponentInput:
    key: str = ""
    part_model_ids: list[uuid.UUID] = strawberry.field(default_factory=list)
    choice_product_ids: list[uuid.UUID] = strawberry.field(default_factory=list)
    fixed_product_id: Optional[uuid.UUID] = None


def _product_editor(product_id: uuid.UUID) -> JSON:
    return _production(lambda: ProductEditor.editor(product_id))


def _product_editor_catalog() -> JSON:
    return ProductEditor.catalog()


def _create_configurable_product(data: BoProductInput) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: ProductEditor.create_configurable(payload))


def _update_product(product_id: uuid.UUID, data: BoProductInput) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: ProductEditor.update_product(product_id, payload))


def _add_product_component(
    product_id: uuid.UUID, key: str, source_type: str, fixed_product_id: Optional[uuid.UUID] = None
) -> JSON:
    return _production(lambda: ProductEditor.add_component(product_id, key, source_type, fixed_product_id))


def _update_product_component(product_id: uuid.UUID, component_id: uuid.UUID, data: BoProductComponentInput) -> JSON:
    payload = strawberry.asdict(data)
    return _production(lambda: ProductEditor.update_component(product_id, component_id, payload))


def _remove_product_component(product_id: uuid.UUID, component_id: uuid.UUID) -> JSON:
    return _production(lambda: ProductEditor.remove_component(product_id, component_id))


_query_fields["product_editor"] = strawberry.field(resolver=_product_editor)
_query_fields["product_editor_catalog"] = strawberry.field(resolver=_product_editor_catalog)
_add_mutation("create_configurable_product", _create_configurable_product)
_add_mutation("save_product", _update_product)
_add_mutation("add_template_step", _add_product_component)
_add_mutation("save_template_step", _update_product_component)
_add_mutation("remove_template_step", _remove_product_component)


# ---------------------------------------------------------------- Catalogue : instruments, pieces, options, values


@strawberry.input
class BoCodeNameInput:
    id: Optional[uuid.UUID] = None
    name: str = ""
    code: str = ""


@strawberry.input
class BoInstrumentModelInput:
    id: Optional[uuid.UUID] = None
    name: str = ""
    instrument_type_id: Optional[uuid.UUID] = None


@strawberry.input
class BoOptionInput:
    id: Optional[uuid.UUID] = None
    name: str = ""
    category: str = ""
    description: str = ""


@strawberry.input
class BoPartModelInput:
    name: str
    code: str
    price: decimal.Decimal
    status: str
    part_type_id: uuid.UUID
    series_id: Optional[uuid.UUID] = None


@strawberry.input
class BoPartModelValueInput:
    id: Optional[uuid.UUID] = None
    option_id: Optional[uuid.UUID] = None
    new_option_name: str = ""
    name: str = ""
    code: str = ""
    price_delta: decimal.Decimal = decimal.Decimal(0)
    active: bool = True


def _catalogue_overview() -> JSON:
    return CatalogueAdmin.overview()


def _catalogue_part_model(part_model_id: uuid.UUID) -> JSON:
    return _production(lambda: CatalogueAdmin.part_model(part_model_id))


def _catalogue_instrument_model(instrument_model_id: uuid.UUID) -> JSON:
    return _production(lambda: CatalogueAdmin.instrument_model(instrument_model_id))


def _catalogue_save_instrument_type(data: BoCodeNameInput) -> JSON:
    return _production(lambda: CatalogueAdmin.save_instrument_type(strawberry.asdict(data)))


def _catalogue_save_instrument_model(data: BoInstrumentModelInput) -> JSON:
    return _production(lambda: CatalogueAdmin.save_instrument_model(strawberry.asdict(data)))


def _catalogue_save_part_type(data: BoCodeNameInput) -> JSON:
    return _production(lambda: CatalogueAdmin.save_part_type(strawberry.asdict(data)))


def _catalogue_save_series(data: BoCodeNameInput) -> JSON:
    return _production(lambda: CatalogueAdmin.save_series(strawberry.asdict(data)))


def _catalogue_save_option(data: BoOptionInput) -> JSON:
    return _production(lambda: CatalogueAdmin.save_option(strawberry.asdict(data)))


def _catalogue_delete_option(option_id: uuid.UUID) -> bool:
    return _production(lambda: CatalogueAdmin.delete_option(option_id))


def _catalogue_save_part_model(part_model_id: uuid.UUID, data: BoPartModelInput) -> JSON:
    return _production(lambda: CatalogueAdmin.save_part_model(part_model_id, strawberry.asdict(data)))


def _catalogue_save_value(part_model_id: uuid.UUID, data: BoPartModelValueInput) -> JSON:
    return _production(lambda: CatalogueAdmin.save_value(part_model_id, strawberry.asdict(data)))


def _catalogue_delete_value(value_id: uuid.UUID) -> JSON:
    return _production(lambda: CatalogueAdmin.delete_value(value_id))


def _catalogue_link(part_model_id: uuid.UUID, instrument_model_id: uuid.UUID, component_id: uuid.UUID) -> bool:
    return _production(lambda: CatalogueAdmin.link(part_model_id, instrument_model_id, component_id))


def _catalogue_unlink(part_model_id: uuid.UUID, instrument_model_id: uuid.UUID, component_id: uuid.UUID) -> bool:
    return _production(lambda: CatalogueAdmin.unlink(part_model_id, instrument_model_id, component_id))


_query_fields["catalogue_overview"] = strawberry.field(resolver=_catalogue_overview)
_query_fields["catalogue_part_model"] = strawberry.field(resolver=_catalogue_part_model)
_query_fields["catalogue_instrument_model"] = strawberry.field(resolver=_catalogue_instrument_model)
_add_mutation("catalogue_save_instrument_type", _catalogue_save_instrument_type)
_add_mutation("catalogue_save_instrument_model", _catalogue_save_instrument_model)
_add_mutation("catalogue_save_part_type", _catalogue_save_part_type)
_add_mutation("catalogue_save_series", _catalogue_save_series)
_add_mutation("catalogue_save_option", _catalogue_save_option)
_add_mutation("catalogue_delete_option", _catalogue_delete_option)
_add_mutation("catalogue_save_part_model", _catalogue_save_part_model)
_add_mutation("catalogue_save_value", _catalogue_save_value)
_add_mutation("catalogue_delete_value", _catalogue_delete_value)
_add_mutation("catalogue_link", _catalogue_link)
_add_mutation("catalogue_unlink", _catalogue_unlink)
_add_mutation("send_payment_link", _send_payment_link)
_add_mutation("ship_order", _ship_order)
_mutation_fields["add_history_event"] = strawberry.mutation(resolver=_add_history_event)
_mutation_fields["delete_history_event"] = strawberry.mutation(resolver=_delete_history_event)
_mutation_fields["set_production_status"] = strawberry.mutation(resolver=_set_production_status)
_add_mutation("link_production_order", _link_production_order)


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
