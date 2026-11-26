"""Instruments and parts made in the workshop, as seen by the back-office.

Building a part gives it its serial number (factory, instrument type, part model, year, batch, counter)
and records what it was made with (part model and option values) in `production_snapshot`.
Building an instrument builds its new parts (or takes parts already made), names the master part
and keeps the configuration it comes from. Each step adds an event to the history.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q
from django.utils import timezone

from ..models import (
    ComponentCompatibility,
    Factory,
    Instrument,
    InstrumentHistory,
    InstrumentModel,
    InstrumentType,
    Order,
    OrderItem,
    Part,
    PartBatch,
    PartEngravingMark,
    PartHistory,
    PartModel,
    PartModelOption,
    PartNFCIdentity,
    SALE_STATUSES,
)
from ..part.part_service import PartService
from ..security import hidden_mark
from . import hidden_mark_service
from ..partBatch.partBatch_service import PartBatchService
from . import order_lines
from .equipment_service import EquipmentService
from ..purchasing.purchasing_service import StockService, part_cost

EVENT_TYPES = [
    ("fabrication", "Fabrication"),
    ("assemblage", "Assemblage"),
    ("reglage", "Réglage"),
    ("controle", "Contrôle qualité"),
    ("reparation", "Réparation"),
    ("modification", "Modification"),
    ("vente", "Vente"),
    ("transfert", "Changement de propriétaire"),
    ("autre", "Autre"),
]
EVENT_LABELS = dict(EVENT_TYPES)
STATUS_LABELS = dict(SALE_STATUSES)
# title of the history event written when the status changes
STATUS_EVENTS = {"sold": "Vendu", "reserved": "Réservé", "in_stock": "Remis en stock"}


def _order_note(item):
    """History note of a sale made for an order line."""
    return f"Commande {order_lines.reference(item.order)} · {item.product_name}" if item else ""


def _text(value):
    return (value or "").strip()


def _owner(email):
    email = _text(email)
    if not email:
        return None
    owner = get_user_model().objects.filter(email__iexact=email).first()
    if owner is None:
        raise ValidationError(f"Aucun compte client avec l'e-mail {email}.")
    return owner


def _user(user):
    # audit fields : only a real staff account
    return user if getattr(user, "is_authenticated", False) else None


class ProductionService:
    # --- what the forms need, in one call ---

    @staticmethod
    def form_data():
        options = PartModelOption.objects.filter(is_active=True).select_related("option").order_by("option__name", "name")
        values_by_model = {}
        for value in options:
            values_by_model.setdefault(value.part_model_id, []).append(value)
        active_batches = {}
        for batch in PartBatch.objects.filter(status="active").order_by("created_at"):
            active_batches[batch.part_model_id] = batch  # the latest one wins, as in PartService

        def option_groups(part_model_id):
            groups = {}
            for value in values_by_model.get(part_model_id, []):
                group = groups.setdefault(
                    value.option_id, {"id": str(value.option_id), "name": value.option.name, "values": []}
                )
                group["values"].append(
                    {"id": str(value.uuid), "name": value.name, "code": value.code, "priceDelta": float(value.price_delta)}
                )
            return list(groups.values())

        part_models = PartModel.objects.select_related("part_type").exclude(status="discontinued").order_by(
            "part_type__name", "name"
        )
        # only the orders that still wait for something from the workshop : the list stays short as orders are served
        unserved_line = (
            OrderItem.objects.filter(order=OuterRef("pk"))
            .annotate(linked=Count("instruments", distinct=True) + Count("parts", distinct=True))
            .filter(linked__lt=F("quantity"))
        )
        orders = list(
            Order.objects.exclude(status__in=["cancelled", "completed"])
            .filter(Exists(unserved_line))
            .select_related("user")
            .prefetch_related("order_items__instruments", "order_items__parts")
            .order_by("-created_at")[:100]
        )
        line_kinds = order_lines.kinds([item for order in orders for item in order.order_items.all()])

        def waits(order):  # a line sold as it is (an accessory) waits for nothing
            return any(
                line_kinds[item.pk] and len(item.instruments.all()) + len(item.parts.all()) < item.quantity
                for item in order.order_items.all()
            )

        orders = [order for order in orders if waits(order)]
        # parts that can go on an instrument : not mounted, not sold alone with an order
        free_parts = ProductionService._free_parts().select_related("part_model")
        return {
            "eventTypes": [{"value": value, "label": label} for value, label in EVENT_TYPES],
            "statuses": [{"value": value, "label": label} for value, label in SALE_STATUSES],
            "factories": [{"id": str(f.uuid), "name": f.name, "code": f.code} for f in Factory.objects.order_by("name")],
            "instrumentTypes": [
                {"id": str(t.uuid), "name": t.name, "code": t.code} for t in InstrumentType.objects.order_by("name")
            ],
            "instrumentModels": [
                {"id": str(m.uuid), "name": m.name, "instrumentType": m.instrument_type.name}
                for m in InstrumentModel.objects.select_related("instrument_type").order_by("name")
            ],
            "partModels": [
                {
                    "id": str(pm.uuid),
                    "name": pm.name,
                    "code": pm.code,
                    "status": pm.status,
                    "price": float(pm.price),
                    "partType": pm.part_type.name,
                    "activeBatch": (
                        {"id": str(active_batches[pm.uuid].uuid), "name": active_batches[pm.uuid].name, "code": active_batches[pm.uuid].code}
                        if pm.uuid in active_batches
                        else None
                    ),
                    "options": option_groups(pm.uuid),
                }
                for pm in part_models
            ],
            "freeParts": [
                {"id": str(p.uuid), "serialNumber": p.serial_number, "partModelId": str(p.part_model_id), "partModel": p.part_model.name}
                for p in free_parts.order_by("-created_at")[:500]
            ],
            "orders": [
                {
                    "id": str(order.uuid),
                    "reference": str(order.uuid)[:8].upper(),
                    "customer": " ".join(filter(None, [order.first_name, order.last_name])) or order.email,
                    "email": order.email,
                    # owner proposed for the instrument : only a customer account can own it
                    "accountEmail": order.user.email if order.user else None,
                    "items": [
                        {
                            "index": index,
                            "name": item.product_name,
                            "parts": ProductionService._parts_of(item.config_snapshot),
                            "quantity": item.quantity,
                            # what the line needs (instrument, part or nothing) and how many are already linked
                            "kind": line_kinds[item.pk],
                            "linked": len(item.instruments.all()) + len(item.parts.all()),
                        }
                        for index, item in enumerate(sorted(order.order_items.all(), key=lambda i: i.pk))
                    ],
                }
                for order in orders
            ],
        }

    @staticmethod
    def _parts_of(config_snapshot):
        """Pieces to make for an order line : every custom piece of the configuration, nested ones included."""
        parts = []

        def walk(snapshot):
            for component in snapshot if isinstance(snapshot, list) else [snapshot] if snapshot else []:
                if not isinstance(component, dict):
                    continue
                if component.get("type") == "custom_piece" and component.get("part_model_id"):
                    parts.append(
                        {
                            "component": component.get("component", ""),
                            "partModelId": str(component["part_model_id"]),
                            "optionIds": [str(o["id"]) for o in component.get("options", []) if o.get("id")],
                        }
                    )
                walk(component.get("snapshot"))

        walk((config_snapshot or {}).get("options"))
        return parts

    # --- building ---

    @staticmethod
    def _snapshot(part_model, option_ids, option_prices=None):
        """What the part is made with, in the same shape as the configurator snapshots.
        The price of each value can differ from the catalogue for this part (option_prices : value id -> supplement) ;
        the catalogue price is kept next to it."""
        option_ids = [str(i) for i in option_ids or []]
        prices = {str(key): Decimal(str(value)) for key, value in (option_prices or {}).items() if value is not None}
        unknown = set(prices) - set(option_ids)
        if unknown:
            raise ValidationError("Un prix est donné pour une valeur qui n'est pas choisie.")
        values = list(PartModelOption.objects.select_related("option").filter(uuid__in=option_ids))
        if len(values) != len(set(option_ids)):
            raise ValidationError("Une des valeurs d'option n'existe plus.")
        seen = set()
        for value in values:
            if value.part_model_id != part_model.uuid:
                raise ValidationError(f"« {value.name} » n'est pas une valeur de {part_model.name}.")
            if value.option_id in seen:
                raise ValidationError(f"{part_model.name} : une seule valeur par option ({value.option.name}).")
            seen.add(value.option_id)
        order = {option_id: index for index, option_id in enumerate(option_ids)}
        values.sort(key=lambda v: order[str(v.uuid)])
        options = []
        for v in values:
            price_delta = prices.get(str(v.uuid), v.price_delta)
            options.append(
                {
                    "id": str(v.uuid),
                    "name": v.option.name,
                    "value": v.name,
                    "code": v.code,
                    "price_delta": str(price_delta),
                    "catalog_price_delta": str(v.price_delta),
                }
            )
        return {
            "type": "custom_piece",
            "part_model": part_model.name,
            "part_model_id": str(part_model.uuid),
            "base_price": str(part_model.price),
            "price": str(part_model.price + sum(Decimal(o["price_delta"]) for o in options)),
            "options": options,
        }

    @staticmethod
    def _prices(rows):
        return {str(row["option_id"]): row["price_delta"] for row in rows or []}

    @staticmethod
    def _make_part(
        part_model_id, factory, instrument_type, option_ids, description, owner, is_master, user, option_prices=None
    ):
        part_model = PartModel.objects.select_related("part_type").filter(pk=part_model_id).first()
        if part_model is None:
            raise ValidationError("Modèle de pièce introuvable.")
        if part_model.status == "discontinued":
            raise ValidationError(f"{part_model.name} n'est plus fabriqué.")
        batch = PartBatch.objects.filter(part_model=part_model, status="active").order_by("-created_at").first()
        if batch is None:
            raise ValidationError(f"Aucun lot actif pour {part_model.name} : crée d'abord un lot.")
        snapshot = ProductionService._snapshot(part_model, option_ids, option_prices)
        # reserves the next number of this part model : the counter stays locked until the end of the transaction
        serial_number = PartService.build_serial_number(factory, part_model, instrument_type, batch)
        part = Part.objects.create(
            serial_number=serial_number,
            part_model=part_model,
            batch=batch,
            owner=owner,
            is_master=is_master,
            description=_text(description),
            production_snapshot=snapshot,
            created_by=user,
            updated_by=user,
        )
        PartHistory.objects.create(
            part=part,
            event_type="fabrication",
            title="Pièce fabriquée",
            description=f"Lot {batch.name} ({batch.code}), atelier {factory.name}.",
            created_by=user,
            updated_by=user,
        )
        return part

    @staticmethod
    @transaction.atomic
    def build_part(data, user=None):
        user = _user(user)
        factory = Factory.objects.filter(pk=data.get("factory_id")).first()
        instrument_type = InstrumentType.objects.filter(pk=data.get("instrument_type_id")).first()
        if factory is None or instrument_type is None:
            raise ValidationError("Choisis l'atelier et le type d'instrument.")
        item = None
        if data.get("order_id"):
            item = order_lines.item_of(data["order_id"], data.get("order_item_index"))
            order_lines.check_room(item, Part)
        part = ProductionService._make_part(
            data.get("part_model_id"),
            factory,
            instrument_type,
            data.get("option_ids"),
            data.get("description"),
            _owner(data.get("owner_email")),
            bool(data.get("is_master")),
            user,
            ProductionService._prices(data.get("option_prices")),
        )
        if item is not None:
            part.order_item = item
            part.save(update_fields=["order_item"])
        # a piece made for an order is already sold
        status = data.get("status") or ("sold" if item else "in_stock")
        ProductionService._check_status(status)
        if status != "in_stock":
            ProductionService._apply_status(part, status, _order_note(item), user)
        return ProductionService.part_sheet(part.uuid)

    @staticmethod
    @transaction.atomic
    def build_instrument(data, user=None):
        user = _user(user)
        model = InstrumentModel.objects.select_related("instrument_type").filter(pk=data.get("instrument_model_id")).first()
        factory = Factory.objects.filter(pk=data.get("factory_id")).first()
        if model is None or factory is None:
            raise ValidationError("Choisis le modèle d'instrument et l'atelier.")
        lines = data.get("parts") or []
        if not lines:
            raise ValidationError("Ajoute au moins une pièce.")
        master_index = data.get("master_index") or 0
        if not 0 <= master_index < len(lines):
            raise ValidationError("Choisis la pièce maîtresse.")
        owner = _owner(data.get("owner_email"))
        item = None
        if data.get("order_id"):
            item = order_lines.item_of(data["order_id"], data.get("order_item_index"))
            order_lines.check_room(item, Instrument)
        # an instrument made for an order is already sold
        status = data.get("status") or ("sold" if item else "in_stock")
        ProductionService._check_status(status)

        existing_ids = [line["existing_part_id"] for line in lines if line.get("existing_part_id")]
        if len(existing_ids) != len(set(existing_ids)):
            raise ValidationError("La même pièce est ajoutée deux fois.")
        existing = {
            p.uuid: p
            for p in Part.objects.select_for_update().filter(uuid__in=existing_ids).select_related("part_model")
        }
        parts = []
        for index, line in enumerate(lines):
            is_master = index == master_index
            if line.get("existing_part_id"):
                part = existing.get(line["existing_part_id"])
                if part is None:
                    raise ValidationError("Une des pièces choisies n'existe plus.")
                if part.instrument_id or Instrument.objects.filter(master_part=part).exists():
                    raise ValidationError(f"La pièce {part.serial_number} est déjà montée sur un instrument.")
                if part.order_item_id:
                    raise ValidationError(f"La pièce {part.serial_number} est vendue seule avec une commande.")
                if is_master and not part.is_master:
                    part.is_master = True
                    part.save(update_fields=["is_master"])
            else:
                part = ProductionService._make_part(
                    line.get("part_model_id"),
                    factory,
                    model.instrument_type,
                    line.get("option_ids"),
                    line.get("description"),
                    owner,
                    is_master,
                    user,
                    ProductionService._prices(line.get("option_prices")),
                )
            parts.append(part)

        master = parts[master_index]
        instrument = Instrument.objects.create(
            instrument_model=model,
            master_part=master,
            owner=owner,
            description=_text(data.get("description")),
            configuration=ProductionService._configuration(item, parts),
            order_item=item,
            created_by=user,
            updated_by=user,
        )
        Part.objects.filter(pk__in=[p.pk for p in parts]).update(instrument=instrument, owner=owner)
        serials = ", ".join(p.serial_number for p in parts)
        InstrumentHistory.objects.create(
            instrument=instrument,
            event_type="assemblage",
            title="Instrument assemblé",
            description=f"{model.name}, pièces : {serials}.",
            created_by=user,
            updated_by=user,
        )
        PartHistory.objects.bulk_create(
            [
                PartHistory(
                    part=part,
                    event_type="assemblage",
                    title="Montée sur un instrument",
                    description=f"{model.name} {master.serial_number}" + (" (pièce maîtresse)" if part is master else ""),
                    created_by=user,
                    updated_by=user,
                )
                for part in parts
            ]
        )
        # the bought pieces of the order (tuners, pickups...) are written on it
        EquipmentService.fill_from_order(instrument, user)
        if status != "in_stock":
            ProductionService._apply_status(instrument, status, _order_note(item), user)
        return ProductionService.instrument_sheet(instrument.uuid)

    @staticmethod
    def _configuration(item, parts):
        if item is not None:
            return {
                "source": "order",
                "orderId": str(item.order.uuid),
                "reference": order_lines.reference(item.order),
                "product": item.product_name,
                "snapshot": item.config_snapshot,
            }
        return {"source": "backoffice", "parts": [part.production_snapshot for part in parts]}

    # --- order lines ---

    @staticmethod
    @transaction.atomic
    def link_order(target, target_id, order_id=None, order_item_index=None, user=None):
        """Gives an instrument, or a piece sold alone, to an order line (made for it or taken from stock) :
        it is sold and belongs to the customer's account. Without an order, takes it back : it returns to stock."""
        user = _user(user)
        model = {"instrument": Instrument, "part": Part}.get(target)
        if model is None:
            raise ValidationError("Attribue un instrument ou une pièce.")
        rows = model.objects.select_for_update(of=("self",)).select_related("order_item__order__user")
        obj = rows.filter(pk=target_id).first()
        if obj is None:
            raise ValidationError("Instrument introuvable." if target == "instrument" else "Pièce introuvable.")
        if target == "part" and obj.instrument_id:
            raise ValidationError("Cette pièce est montée sur un instrument : c'est l'instrument qui va à la commande.")
        if order_id:
            item = order_lines.item_of(order_id, order_item_index)
            if obj.order_item_id != item.pk:
                order_lines.check_room(item, model, exclude_pk=obj.pk)
                if obj.order_item_id:
                    ProductionService._unlink(obj, "in_stock", user)
                ProductionService._link(obj, item, user)
        elif obj.order_item_id:
            ProductionService._unlink(obj, "in_stock", user)
        if target == "instrument":
            return ProductionService.instrument_sheet(obj.uuid)
        return ProductionService.part_sheet(obj.uuid)

    @staticmethod
    def release_order(order, user=None):
        """Cancelled order : what was made or kept for it goes back to stock (and to no customer)."""
        user = _user(user)
        for model in (Instrument, Part):
            for obj in model.objects.select_for_update(of=("self",)).select_related("order_item__order__user").filter(
                order_item__order=order
            ):
                ProductionService._unlink(obj, "in_stock", user, cancelled=True)

    @staticmethod
    def _link(obj, item, user):
        order = item.order
        obj.order_item = item
        fields = ["order_item"]
        # the customer's account owns it, unless an owner was already chosen
        if obj.owner_id is None and order.user_id:
            obj.owner = order.user
            fields.append("owner")
            if isinstance(obj, Instrument):
                Part.objects.filter(instrument=obj).update(owner=order.user)
        obj.save(update_fields=fields)
        if isinstance(obj, Instrument):
            EquipmentService.fill_from_order(obj, user)
        note = _order_note(item)
        if obj.status != "sold":
            ProductionService._apply_status(obj, "sold", note, user)
        else:
            ProductionService._history(obj, "vente", "Attribué à une commande", note, user)

    @staticmethod
    def _unlink(obj, status, user, cancelled=False):
        order = obj.order_item.order
        reference = order_lines.reference(order)
        obj.order_item = None
        fields = ["order_item"]
        if order.user_id and obj.owner_id == order.user_id:
            obj.owner = None
            fields.append("owner")
            if isinstance(obj, Instrument):
                Part.objects.filter(instrument=obj).update(owner=None)
        obj.save(update_fields=fields)
        note = f"Commande {reference} annulée." if cancelled else f"Retiré de la commande {reference}."
        if obj.status != status:
            ProductionService._apply_status(obj, status, note, user)
        else:
            ProductionService._history(obj, "vente", "Retiré d'une commande", note, user)

    @staticmethod
    def _history(obj, event_type, title, description, user):
        event = {"event_type": event_type, "title": title, "description": description, "created_by": user, "updated_by": user}
        if isinstance(obj, Instrument):
            InstrumentHistory.objects.create(instrument=obj, **event)
        else:
            PartHistory.objects.create(part=obj, **event)

    # --- editing ---

    @staticmethod
    def update_instrument(instrument_id, description=None, owner_email=None, user=None):
        instrument = Instrument.objects.filter(pk=instrument_id).first()
        if instrument is None:
            raise ValidationError("Instrument introuvable.")
        user = _user(user)
        with transaction.atomic():
            if description is not None:
                instrument.description = _text(description)
            if owner_email is not None:
                owner = _owner(owner_email)
                if owner != instrument.owner:
                    InstrumentHistory.objects.create(
                        instrument=instrument,
                        event_type="transfert",
                        title="Changement de propriétaire",
                        description=owner.email if owner else "Plus de propriétaire",
                        created_by=user,
                        updated_by=user,
                    )
                instrument.owner = owner
                Part.objects.filter(instrument=instrument).update(owner=owner)
            instrument.updated_by = user
            instrument.save()
        return ProductionService.instrument_sheet(instrument.uuid)

    @staticmethod
    def update_part(part_id, description, user=None):
        updated = Part.objects.filter(pk=part_id).update(description=_text(description), updated_by=_user(user))
        if not updated:
            raise ValidationError("Pièce introuvable.")
        return ProductionService.part_sheet(part_id)

    # --- replacing a manufactured part ---

    @staticmethod
    def _free_parts():
        """Parts that can go on an instrument : not mounted, not sold alone with an order."""
        return Part.objects.filter(instrument__isnull=True, instrument_masterpart__isnull=True, order_item__isnull=True)

    @staticmethod
    def _compatible_models(instrument, part):
        """Part models that can take this part's place on the instrument : those the catalogue declares compatible
        with the instrument model (Compatibilité), of the same type, plus the model already mounted.
        None when the catalogue declares nothing for this type on this model : every model of the type is then let in."""
        declared = set(
            ComponentCompatibility.objects.filter(
                instrument_model_id=instrument.instrument_model_id,
                part_model__part_type_id=part.part_model.part_type_id,
            ).values_list("part_model_id", flat=True)
        )
        return declared | {part.part_model_id} if declared else None

    @staticmethod
    def replacement_parts(part_id):
        """Free parts that can take the place of a mounted one : same type, compatible with the instrument model
        when the catalogue says which ones are, same model first."""
        part = Part.objects.select_related("part_model", "instrument").filter(pk=part_id).first()
        if part is None or part.instrument is None:
            raise ValidationError("Cette pièce n'est montée sur aucun instrument.")
        models = ProductionService._compatible_models(part.instrument, part)
        rows = ProductionService._free_parts().filter(part_model__part_type_id=part.part_model.part_type_id)
        if models is not None:
            rows = rows.filter(part_model_id__in=models)
        rows = sorted(
            rows.select_related("part_model").order_by("-created_at")[:300],
            key=lambda p: p.part_model_id != part.part_model_id,
        )
        return {
            # false : nothing declared for this type in Compatibilité, every model of the type is listed
            "checked": models is not None,
            "parts": [
                {
                    "id": str(p.uuid),
                    "serialNumber": p.serial_number,
                    "partModel": p.part_model.name,
                    "sameModel": p.part_model_id == part.part_model_id,
                    "options": ", ".join(
                        f"{o.get('name', '')} : {o.get('value', '')}"
                        for o in (p.production_snapshot or {}).get("options", [])
                        if o.get("value")
                    ),
                }
                for p in rows
            ],
        }

    @staticmethod
    @transaction.atomic
    def replace_part(instrument_id, part_id, new_part_id, note="", user=None):
        """Takes a part off the instrument and mounts a free one of the same kind in its place. The old part goes
        back to stock (free again), the new one follows the instrument (owner, sold or not). Both stay in history."""
        user = _user(user)
        instrument = (
            Instrument.objects.select_for_update(of=("self",)).select_related("master_part", "instrument_model")
            .filter(pk=instrument_id)
            .first()
        )
        if instrument is None:
            raise ValidationError("Instrument introuvable.")
        parts = {p.uuid: p for p in Part.objects.select_for_update().select_related("part_model").filter(uuid__in=[part_id, new_part_id])}
        old, new = parts.get(part_id), parts.get(new_part_id)
        if old is None or old.instrument_id != instrument.uuid:
            raise ValidationError("Cette pièce n'est plus montée sur cet instrument.")
        if old.uuid == instrument.master_part_id:
            raise ValidationError(
                "La pièce maîtresse porte le numéro de série de l'instrument : elle ne se remplace pas."
            )
        if new is None:
            raise ValidationError("La pièce de remplacement n'existe plus.")
        if not ProductionService._free_parts().filter(pk=new.uuid).exists():
            raise ValidationError(f"La pièce {new.serial_number} est déjà montée ou vendue avec une commande.")
        if new.part_model.part_type_id != old.part_model.part_type_id:
            raise ValidationError("La pièce de remplacement doit être du même type.")
        models = ProductionService._compatible_models(instrument, old)
        if models is not None and new.part_model_id not in models:
            raise ValidationError(
                f"{new.part_model.name} n'est pas compatible avec le modèle {instrument.instrument_model.name} "
                "(voir Compatibilité dans le catalogue)."
            )
        note = _text(note)[:255]
        serial = instrument.master_part.serial_number

        old.instrument, old.owner, old.status, old.sold_at, old.updated_by = None, None, "in_stock", None, user
        old.save(update_fields=["instrument", "owner", "status", "sold_at", "updated_by", "updated_at"])
        new.instrument, new.owner, new.updated_by = instrument, instrument.owner, user
        new.status, new.sold_at = instrument.status, instrument.sold_at
        new.save(update_fields=["instrument", "owner", "status", "sold_at", "updated_by", "updated_at"])

        change = f"{old.part_model.name} : {old.serial_number} → {new.serial_number}"
        ProductionService._history(
            instrument, "modification", "Pièce remplacée", f"{change}." + (f" {note}" if note else ""), user
        )
        ProductionService._history(
            old, "modification", f"Démontée de l'instrument {serial}",
            f"Remplacée par {new.serial_number}." + (f" {note}" if note else ""), user,
        )
        ProductionService._history(
            new, "assemblage", "Montée sur un instrument",
            f"{instrument.instrument_model.name} {serial} (remplace {old.serial_number})." + (f" {note}" if note else ""),
            user,
        )
        return ProductionService.instrument_sheet(instrument.uuid)

    # --- sold or not ---

    @staticmethod
    def _check_status(status):
        if status not in STATUS_LABELS:
            raise ValidationError("Statut inconnu.")

    @staticmethod
    @transaction.atomic
    def set_status(target, target_id, status, note="", user=None):
        """Sold, reserved or back in stock. Writes the change in the history ; an instrument takes its parts with it."""
        ProductionService._check_status(status)
        model = {"instrument": Instrument, "part": Part}.get(target)
        if model is None:
            raise ValidationError("Change le statut d'un instrument ou d'une pièce.")
        obj = model.objects.select_for_update().filter(pk=target_id).first()
        if obj is None:
            raise ValidationError("Instrument introuvable." if target == "instrument" else "Pièce introuvable.")
        if obj.status != status:
            ProductionService._apply_status(obj, status, note, _user(user))
        if target == "instrument":
            return ProductionService.instrument_sheet(obj.uuid)
        return ProductionService.part_sheet(obj.uuid)

    @staticmethod
    def _apply_status(obj, status, note, user):
        sold_at = timezone.now() if status == "sold" else None
        obj.status, obj.sold_at, obj.updated_by = status, sold_at, user
        obj.save(update_fields=["status", "sold_at", "updated_by", "updated_at"])
        title = STATUS_EVENTS[status]
        description = _text(note) or (f"Propriétaire : {obj.owner.email}" if status == "sold" and obj.owner else "")
        event = {"event_type": "vente", "title": title, "created_by": user, "updated_by": user}
        if isinstance(obj, Instrument):
            InstrumentHistory.objects.create(instrument=obj, description=description, **event)
            parts = list(Part.objects.filter(instrument=obj))
            Part.objects.filter(instrument=obj).update(status=status, sold_at=sold_at, updated_by=user)
            serial = obj.master_part.serial_number
            PartHistory.objects.bulk_create(
                [PartHistory(part=part, description=f"Avec l'instrument {serial}.", **event) for part in parts]
            )
        else:
            PartHistory.objects.create(part=obj, description=description, **event)

    @staticmethod
    def create_batch(part_model_id, name, code):
        name, code = _text(name), _text(code).upper()
        if not name or not code or len(code) > 5:
            raise ValidationError("Donne un nom et un code de 5 caractères maximum au lot.")
        if not PartModel.objects.filter(pk=part_model_id).exists():
            raise ValidationError("Modèle de pièce introuvable.")
        batch = PartBatchService.create(part_model_id, name, code)
        return {"id": str(batch.uuid), "name": batch.name, "code": batch.code}

    # --- history ---

    @staticmethod
    def add_event(target, target_id, event_type, title, description, user=None):
        if event_type not in EVENT_LABELS:
            raise ValidationError("Type d'événement inconnu.")
        title = _text(title) or EVENT_LABELS[event_type]
        if len(title) > 100:
            raise ValidationError("Le titre fait 100 caractères au plus.")
        user = _user(user)
        fields = {
            "event_type": event_type,
            "title": title,
            "description": _text(description),
            "created_by": user,
            "updated_by": user,
        }
        if target == "instrument":
            instrument = Instrument.objects.filter(pk=target_id).first()
            if instrument is None:
                raise ValidationError("Instrument introuvable.")
            event = InstrumentHistory.objects.create(instrument=instrument, **fields)
        elif target == "part":
            part = Part.objects.filter(pk=target_id).first()
            if part is None:
                raise ValidationError("Pièce introuvable.")
            event = PartHistory.objects.create(part=part, **fields)
        else:
            raise ValidationError("Ajoute l'événement à un instrument ou à une pièce.")
        return ProductionService._event(event)

    @staticmethod
    def delete_event(event_id):
        deleted = InstrumentHistory.objects.filter(pk=event_id).delete()[0] or PartHistory.objects.filter(pk=event_id).delete()[0]
        if not deleted:
            raise ValidationError("Événement introuvable.")
        return True

    @staticmethod
    def _event(event, part=None):
        author = event.created_by
        return {
            "id": str(event.uuid),
            "eventType": event.event_type,
            "eventLabel": EVENT_LABELS.get(event.event_type, event.event_type),
            "title": event.title,
            "description": event.description,
            "createdAt": event.created_at.isoformat(),
            "author": (author.get_full_name() or author.email or author.username) if author else "",
            "part": {"id": str(part.uuid), "serialNumber": part.serial_number, "partModel": part.part_model.name}
            if part
            else None,
        }

    # --- lists and sheets ---

    @staticmethod
    def _part_row(part):
        snapshot = part.production_snapshot or {}
        instrument = getattr(part, "instrument", None)
        return {
            "id": str(part.uuid),
            "serialNumber": part.serial_number,
            "partModel": {"id": str(part.part_model_id), "name": part.part_model.name, "code": part.part_model.code},
            "partType": part.part_model.part_type.name,
            "isMaster": part.is_master,
            "status": part.status,
            "soldAt": part.sold_at.isoformat() if part.sold_at else None,
            "description": part.description,
            "options": [
                {
                    "option": o.get("name", ""),
                    "value": o.get("value", ""),
                    "priceDelta": float(o["price_delta"]) if o.get("price_delta") not in (None, "") else None,
                    "catalogPriceDelta": float(o["catalog_price_delta"]) if o.get("catalog_price_delta") not in (None, "") else None,
                }
                for o in snapshot.get("options", [])
            ],
            "price": float(snapshot["price"]) if snapshot.get("price") not in (None, "") else None,
            "batch": {"name": part.batch.name, "code": part.batch.code},
            "createdAt": part.created_at.isoformat(),
            "instrument": {"id": str(instrument.uuid), "model": instrument.instrument_model.name} if instrument else None,
            "owner": part.owner.email if part.owner else None,
            # piece sold alone : its order line (a mounted part follows its instrument's order)
            "order": order_lines.serialize(part.order_item) if part.order_item_id else None,
            # what it cost : the supplier invoice line that paid the factory for it
            "purchase": part_cost(part),
        }

    @staticmethod
    def instruments(offset=0, limit=50, search=None, status=None):
        rows = Instrument.objects.select_related(
            "instrument_model__instrument_type", "master_part", "owner", "order_item__order"
        ).annotate(part_count=Count("instrument_parts"))
        if status:
            rows = rows.filter(status=status)
        text = _text(search)
        if text:
            rows = rows.filter(
                Q(instrument_parts__serial_number__icontains=text)
                | Q(instrument_model__name__icontains=text)
                | Q(owner__email__icontains=text)
                | Q(description__icontains=text)
            ).distinct()
        limit = max(1, min(limit, 200))
        return {
            "totalCount": rows.count(),
            "results": [
                {
                    "id": str(i.uuid),
                    "serialNumber": i.master_part.serial_number,
                    "model": i.instrument_model.name,
                    "instrumentType": i.instrument_model.instrument_type.name,
                    "owner": i.owner.email if i.owner else None,
                    "description": i.description,
                    "partCount": i.part_count,
                    "status": i.status,
                    "order": order_lines.serialize(i.order_item),
                    "createdAt": i.created_at.isoformat(),
                }
                for i in rows.order_by("-created_at")[offset : offset + limit]
            ],
        }

    @staticmethod
    def instrument_sheet(instrument_id):
        parts = Part.objects.select_related(
            "part_model__part_type", "batch", "owner", "purchase_line__invoice__supplier"
        ).order_by("-is_master", "created_at")
        instrument = (
            Instrument.objects.select_related("instrument_model__instrument_type", "master_part", "owner", "order_item__order")
            .prefetch_related(
                Prefetch("instrument_parts", queryset=parts),
                Prefetch("history", queryset=InstrumentHistory.objects.select_related("created_by")),
                Prefetch("instrument_parts__history", queryset=PartHistory.objects.select_related("created_by")),
            )
            .filter(pk=instrument_id)
            .first()
        )
        if instrument is None:
            return None
        part_list = list(instrument.instrument_parts.all())
        history = [ProductionService._event(e) for e in instrument.history.all()]
        history += [ProductionService._event(e, part) for part in part_list for e in part.history.all()]
        history.sort(key=lambda e: e["createdAt"], reverse=True)
        for part in part_list:
            part.instrument = instrument  # already loaded : no query per part
        return {
            "id": str(instrument.uuid),
            "serialNumber": instrument.master_part.serial_number,
            "model": instrument.instrument_model.name,
            "instrumentType": instrument.instrument_model.instrument_type.name,
            "owner": instrument.owner.email if instrument.owner else None,
            "description": instrument.description,
            "status": instrument.status,
            "soldAt": instrument.sold_at.isoformat() if instrument.sold_at else None,
            "configuration": instrument.configuration,
            "order": order_lines.serialize(instrument.order_item),
            "createdAt": instrument.created_at.isoformat(),
            "parts": [ProductionService._part_row(part) for part in part_list],
            "equipment": EquipmentService.rows(instrument.uuid),
            "costs": ProductionService._costs(instrument.uuid, part_list),
            "history": history,
        }

    @staticmethod
    def _costs(instrument_id, part_list):
        """What the instrument cost : its pieces paid to the factory (invoices) and the bought pieces taken out of
        the workshop stock. Pieces with no invoice yet are counted apart."""
        costs = [part_cost(part) for part in part_list]
        known = [c for c in costs if c]
        stock = StockService.instrument_cost(instrument_id)["total"]
        parts_ht = round(sum(c["unitHt"] for c in known), 2)
        return {
            "partsHt": parts_ht,
            "partsTtc": round(sum(c["unitTtc"] for c in known), 2),
            "partsWithoutInvoice": len(costs) - len(known),
            "stockHt": stock,
            "totalHt": round(parts_ht + stock, 2),
        }

    @staticmethod
    def parts(offset=0, limit=50, search=None, free_only=False, status=None):
        rows = Part.objects.select_related(
            "part_model__part_type",
            "batch",
            "owner",
            "instrument__instrument_model",
            "order_item__order",
            "purchase_line__invoice__supplier",
        )
        if free_only:
            rows = rows.filter(instrument__isnull=True)
        if status:
            rows = rows.filter(status=status)
        text = _text(search)
        if text:
            rows = rows.filter(
                Q(serial_number__icontains=text)
                | Q(part_model__name__icontains=text)
                | Q(part_model__code__icontains=text)
                | Q(description__icontains=text)
            )
        limit = max(1, min(limit, 200))
        return {
            "totalCount": rows.count(),
            "results": [ProductionService._part_row(p) for p in rows.order_by("-created_at")[offset : offset + limit]],
        }

    @staticmethod
    def part_sheet(part_id):
        part = (
            Part.objects.select_related(
                "part_model__part_type",
                "batch",
                "owner",
                "instrument__instrument_model",
                "order_item__order",
                "purchase_line__invoice__supplier",
            )
            .prefetch_related(
                Prefetch("history", queryset=PartHistory.objects.select_related("created_by")),
                Prefetch("part_identities", queryset=PartNFCIdentity.objects.select_related("batch").order_by("-created_at")),
                Prefetch(
                    "security_marks",
                    queryset=PartEngravingMark.objects.filter(mark_type="security").order_by("-created_at"),
                    to_attr="hidden_marks",
                ),
            )
            .filter(pk=part_id)
            .first()
        )
        if part is None:
            return None
        return {
            **ProductionService._part_row(part),
            "identities": [ProductionService._identity(i) for i in part.part_identities.all()],
            "history": [ProductionService._event(e) for e in part.history.all()],
            # place of the hidden code already known (from the engraving agent), else written when the engraving is checked
            "hiddenMarkLocation": hidden_mark_service.location_to_show(part, part.hidden_marks),
            # places proposed in that free field (from the "security" engraving template)
            "hiddenMarkSuggestions": hidden_mark_service.suggestions(part),
            # where and when the hidden code was engraved ; the code itself is never shown
            "hiddenMarks": [
                {
                    "location": mark.location,
                    "status": mark.status,
                    "confirmedAt": mark.confirmed_at.isoformat() if mark.confirmed_at else None,
                }
                for mark in part.hidden_marks
            ],
        }

    @staticmethod
    def check_hidden_mark(part_id, code):
        """Says whether the code read on the part is its hidden code (to check a part whose NFC tag no longer works)."""
        part = Part.objects.filter(pk=part_id).first()
        if part is None:
            raise ValidationError("Pièce introuvable.")
        if not hidden_mark.normalize(code or ""):
            raise ValidationError("Saisis le code lu sur la pièce.")
        try:
            match = hidden_mark.matches(part, code)
        except Exception as error:
            raise ValidationError(f"Clé du modèle illisible dans Vault ({error.__class__.__name__}).") from error
        return {"match": match, "serialNumber": part.serial_number}

    @staticmethod
    def _identity(identity):
        """NFC tag linked to a part, read only : the keys stay in Vault, only the tag and its state are shown."""
        def when(value):
            return value.isoformat() if value else None

        return {
            "nfcUid": identity.nfc_uid,
            "status": identity.status,
            "keyVersion": identity.key_version,
            "batch": identity.batch.code,
            "lastSeenCounter": identity.last_seen_counter,
            "lastVerifiedAt": when(identity.last_verified_at),
            "createdAt": when(identity.created_at),
            "revokedAt": when(identity.revoked_at),
        }
