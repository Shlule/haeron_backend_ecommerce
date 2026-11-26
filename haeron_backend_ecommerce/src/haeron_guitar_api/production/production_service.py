"""Instruments and parts made in the workshop, as seen by the back-office.

Building a part gives it its serial number (factory, instrument type, part model, year, batch, counter)
and records what it was made with (part model and option values) in `production_snapshot`.
Building an instrument builds its new parts (or takes parts already made), names the master part
and keeps the configuration it comes from. Each step adds an event to the history.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from ..models import (
    Factory,
    Instrument,
    InstrumentHistory,
    InstrumentModel,
    InstrumentType,
    Order,
    Part,
    PartBatch,
    PartHistory,
    PartModel,
    PartModelOption,
    SALE_STATUSES,
    SerialCounter,
)
from ..part.part_service import PartService
from ..partBatch.partBatch_service import PartBatchService

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
        orders = Order.objects.exclude(status="cancelled").select_related("user").prefetch_related("order_items").order_by(
            "-created_at"
        )[:100]
        free_parts = Part.objects.filter(instrument__isnull=True, instrument_masterpart__isnull=True).select_related(
            "part_model"
        )
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
                        {"index": index, "name": item.product_name, "parts": ProductionService._parts_of(item.config_snapshot)}
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
    def _snapshot(part_model, option_ids):
        """What the part is made with, in the same shape as the configurator snapshots."""
        option_ids = [str(i) for i in option_ids or []]
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
        return {
            "type": "custom_piece",
            "part_model": part_model.name,
            "part_model_id": str(part_model.uuid),
            "options": [{"id": str(v.uuid), "name": v.option.name, "value": v.name, "code": v.code} for v in values],
        }

    @staticmethod
    def _make_part(part_model_id, factory, instrument_type, option_ids, description, owner, is_master, user):
        part_model = PartModel.objects.select_related("part_type").filter(pk=part_model_id).first()
        if part_model is None:
            raise ValidationError("Modèle de pièce introuvable.")
        if part_model.status == "discontinued":
            raise ValidationError(f"{part_model.name} n'est plus fabriqué.")
        batch = PartBatch.objects.filter(part_model=part_model, status="active").order_by("-created_at").first()
        if batch is None:
            raise ValidationError(f"Aucun lot actif pour {part_model.name} : crée d'abord un lot.")
        snapshot = ProductionService._snapshot(part_model, option_ids)
        # the counter row is locked until the end of the transaction : two parts never get the same number
        SerialCounter.objects.get_or_create(factory=factory, year=timezone.now().year)
        SerialCounter.objects.select_for_update().get(factory=factory, year=timezone.now().year)
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
        from ..serial_counter.serial_counter_service import SerialCounterService

        SerialCounterService.next(factory.uuid)
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
        part = ProductionService._make_part(
            data.get("part_model_id"),
            factory,
            instrument_type,
            data.get("option_ids"),
            data.get("description"),
            _owner(data.get("owner_email")),
            bool(data.get("is_master")),
            user,
        )
        status = data.get("status") or "in_stock"
        ProductionService._check_status(status)
        if status != "in_stock":
            ProductionService._apply_status(part, status, "", user)
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
        # an instrument made for an order is already sold
        status = data.get("status") or ("sold" if data.get("order_id") else "in_stock")
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
                )
            parts.append(part)

        master = parts[master_index]
        instrument = Instrument.objects.create(
            instrument_model=model,
            master_part=master,
            owner=owner,
            description=_text(data.get("description")),
            configuration=ProductionService._configuration(data, parts),
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
        if status != "in_stock":
            ProductionService._apply_status(instrument, status, "", user)
        return ProductionService.instrument_sheet(instrument.uuid)

    @staticmethod
    def _configuration(data, parts):
        order_id, item_index = data.get("order_id"), data.get("order_item_index")
        if order_id:
            order = Order.objects.filter(uuid=order_id).prefetch_related("order_items").first()
            items = sorted(order.order_items.all(), key=lambda i: i.pk) if order else []
            if item_index is None or not 0 <= item_index < len(items):
                raise ValidationError("Ligne de commande introuvable.")
            item = items[item_index]
            return {
                "source": "order",
                "orderId": str(order.uuid),
                "reference": str(order.uuid)[:8].upper(),
                "product": item.product_name,
                "snapshot": item.config_snapshot,
            }
        return {"source": "backoffice", "parts": [part.production_snapshot for part in parts]}

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
            "options": [{"option": o.get("name", ""), "value": o.get("value", "")} for o in snapshot.get("options", [])],
            "batch": {"name": part.batch.name, "code": part.batch.code},
            "createdAt": part.created_at.isoformat(),
            "instrument": {"id": str(instrument.uuid), "model": instrument.instrument_model.name} if instrument else None,
            "owner": part.owner.email if part.owner else None,
        }

    @staticmethod
    def instruments(offset=0, limit=50, search=None, status=None):
        rows = Instrument.objects.select_related("instrument_model__instrument_type", "master_part", "owner").annotate(
            part_count=Count("instrument_parts")
        )
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
                    "createdAt": i.created_at.isoformat(),
                }
                for i in rows.order_by("-created_at")[offset : offset + limit]
            ],
        }

    @staticmethod
    def instrument_sheet(instrument_id):
        parts = Part.objects.select_related("part_model__part_type", "batch", "owner").order_by("-is_master", "created_at")
        instrument = (
            Instrument.objects.select_related("instrument_model__instrument_type", "master_part", "owner")
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
            "createdAt": instrument.created_at.isoformat(),
            "parts": [ProductionService._part_row(part) for part in part_list],
            "history": history,
        }

    @staticmethod
    def parts(offset=0, limit=50, search=None, free_only=False, status=None):
        rows = Part.objects.select_related("part_model__part_type", "batch", "owner", "instrument__instrument_model")
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
            Part.objects.select_related("part_model__part_type", "batch", "owner", "instrument__instrument_model")
            .prefetch_related(Prefetch("history", queryset=PartHistory.objects.select_related("created_by")))
            .filter(pk=part_id)
            .first()
        )
        if part is None:
            return None
        return {
            **ProductionService._part_row(part),
            "history": [ProductionService._event(e) for e in part.history.all()],
        }
