"""
Equipment of an instrument : the bought hardware mounted on it (tuners, pickups, bridge, selector, pots, jack).
It has no serial number (we do not make it) : each row says what is mounted in which place, since when, and where
it comes from (the order configuration and/or the workshop stock). Replacing or removing a piece keeps its row with
a removal date and writes it in the instrument's history, so the sheet tells what was mounted and what was changed.
"""

import unicodedata
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import (
    EQUIPMENT_SLOTS,
    Instrument,
    InstrumentEquipment,
    InstrumentHistory,
    Product,
    StockItem,
    StockMovement,
)
from ..purchasing.purchasing_service import StockService

SLOT_LABELS = dict(EQUIPMENT_SLOTS)

# beginnings of the words found in a configurator component key, a product name or a stock family, for each place
_SLOT_WORDS = [
    ("mecaniques", ("mecanique", "tuner", "machine")),
    ("micros", ("mic", "pickup", "humbucker", "single", "p90")),
    ("chevalet", ("chevalet", "bridge", "vibrato", "tremolo", "cordier", "tailpiece")),
    ("selecteur", ("selecteur", "toggle", "commutateur", "switch")),
    ("potentiometres", ("potentiometre", "pot", "volume", "tonalite", "knob", "bouton")),
    ("jack", ("jack", "output", "sortie")),
]


def _plain(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return "".join(c if c.isalnum() else " " for c in text)


def slot_of(*texts):
    """The place a piece goes in, read from its component key, name or stock family ('autre' when unknown).
    The first word that names a place decides : a « micro chevalet » is a pickup, a « jack Switchcraft » a jack."""
    for text in texts:
        for word in _plain(text).split():
            for slot, keys in _SLOT_WORDS:
                if any(word.startswith(key) for key in keys):
                    return slot
    return "autre"


def from_snapshot(config_snapshot):
    """Bought pieces of an order line configuration : fixed components and product choices, nested ones included
    (custom pieces are manufactured parts, they get a serial number instead)."""
    entries = []

    def walk(node):
        if isinstance(node, list):
            for child in node:
                walk(child)
            return
        if not isinstance(node, dict):
            return
        kind = node.get("type")
        if kind in ("fixed", "product_choice") or (kind is None and node.get("component") and node.get("name")):
            entries.append(
                {
                    "slot": slot_of(node.get("component"), node.get("name")),
                    "name": str(node.get("name") or node.get("component") or "")[:255],
                    "product_id": node.get("product_id"),
                    "component": node.get("component", ""),
                }
            )
        if kind == "custom_piece":
            return
        for key in ("options", "snapshot", "items"):
            walk(node.get(key))

    walk(config_snapshot)
    return [entry for entry in entries if entry["name"]]


def _product_id(value):
    """The catalogue product of a snapshot entry, if it still exists."""
    try:
        product_id = uuid.UUID(str(value))
    except ValueError:
        return None
    return product_id if Product.objects.filter(pk=product_id).exists() else None


def _history(instrument, event_type, title, description, user):
    InstrumentHistory.objects.create(
        instrument=instrument,
        event_type=event_type,
        title=title,
        description=description,
        created_by=user,
        updated_by=user,
    )


def _with_note(text, note):
    return f"{text} ({note})." if note else f"{text}."


def _take_from_stock(instrument, stock_item_id, quantity, note, user):
    """Takes the piece out of the workshop stock for this instrument : its cost goes to the instrument."""
    StockService.move(
        {
            "stock_item_id": stock_item_id,
            "kind": "use",
            "zone": "workshop",
            "quantity": quantity or "1",
            "instrument_id": instrument.uuid,
            "note": note,
        },
        user,
    )
    return (
        StockMovement.objects.filter(stock_item_id=stock_item_id, instrument=instrument, kind="use")
        .order_by("-occurred_at", "-created_at")
        .first()
    )


class EquipmentService:
    @staticmethod
    def slots():
        return [{"value": value, "label": label} for value, label in EQUIPMENT_SLOTS]

    @staticmethod
    def fill_from_order(instrument, user=None):
        """Writes the bought pieces of the instrument's order line on it, those not already there. Returns how many."""
        item = instrument.order_item
        if item is None:
            return 0
        # already there, or already written from the order and changed since (a replaced piece does not come back)
        current = {
            (row.slot, row.name.lower())
            for row in InstrumentEquipment.objects.filter(instrument=instrument)
            if row.removed_at is None or row.from_order
        }
        now = timezone.now()
        rows = []
        for entry in from_snapshot(item.config_snapshot):
            if (entry["slot"], entry["name"].lower()) in current:
                continue
            current.add((entry["slot"], entry["name"].lower()))
            rows.append(
                InstrumentEquipment(
                    instrument=instrument,
                    slot=entry["slot"],
                    name=entry["name"],
                    product_id=_product_id(entry["product_id"]),
                    from_order=True,
                    installed_at=now,
                    created_by=user,
                    updated_by=user,
                )
            )
        InstrumentEquipment.objects.bulk_create(rows)
        return len(rows)

    @staticmethod
    @transaction.atomic
    def fill_from_order_of(instrument_id, user=None):
        """Back-office action : writes the order's pieces not yet on the instrument (an instrument assembled before)."""
        rows = Instrument.objects.select_for_update(of=("self",)).select_related("order_item")
        instrument = rows.filter(pk=instrument_id).first()
        if instrument is None:
            raise ValidationError("Instrument introuvable.")
        if instrument.order_item_id is None:
            raise ValidationError("Cet instrument n'est attribué à aucune commande.")
        return EquipmentService.fill_from_order(instrument, user)

    @staticmethod
    @transaction.atomic
    def mount(instrument_id, data, user=None):
        """Mounts a piece (taken from the workshop stock or typed), in addition to what is there or in place of a row."""
        instrument = Instrument.objects.select_for_update().filter(pk=instrument_id).first()
        if instrument is None:
            raise ValidationError("Instrument introuvable.")
        item = None
        if data.get("stock_item_id"):
            item = StockItem.objects.filter(pk=data["stock_item_id"]).first()
            if item is None:
                raise ValidationError("Article introuvable.")
        replaced = None
        if data.get("replaces_id"):
            replaced = InstrumentEquipment.objects.filter(
                pk=data["replaces_id"], instrument=instrument, removed_at__isnull=True
            ).first()
            if replaced is None:
                raise ValidationError("L'équipement à remplacer n'est plus monté sur cet instrument.")
        slot = data.get("slot") or (replaced.slot if replaced else slot_of(item.family, item.name) if item else "")
        if slot not in SLOT_LABELS:
            raise ValidationError("Choisis l'emplacement (mécaniques, micros, chevalet…).")
        name = (data.get("name") or "").strip() or (item.name if item else "")
        if not name:
            raise ValidationError("Indique ce qui est monté, ou choisis un article du stock.")
        if len(name) > 255:
            raise ValidationError("Le nom fait 255 caractères au plus.")
        note = (data.get("note") or "").strip()[:255]

        movement = _take_from_stock(instrument, item.uuid, data.get("quantity"), note, user) if item else None
        now = timezone.now()
        if replaced is not None:
            replaced.removed_at = now
            replaced.removal_note = f"Remplacé par {name}"[:255]
            replaced.updated_by = user
            replaced.save(update_fields=["removed_at", "removal_note", "updated_by", "updated_at"])
        row = InstrumentEquipment.objects.create(
            instrument=instrument,
            slot=slot,
            name=name,
            stock_item=item,
            stock_movement=movement,
            note=note,
            installed_at=now,
            created_by=user,
            updated_by=user,
        )
        label = SLOT_LABELS[slot]
        if replaced is not None:
            _history(
                instrument, "modification", f"{label} : pièce remplacée", _with_note(f"{replaced.name} → {name}", note), user
            )
        else:
            _history(instrument, "modification", f"{label} : pièce montée", _with_note(name, note), user)
        return row

    @staticmethod
    @transaction.atomic
    def take_from_stock(equipment_id, stock_item_id, quantity=None, user=None):
        """A piece already listed (from the order) is taken out of the workshop stock : nothing changes on the
        instrument, its cost goes to it."""
        row = InstrumentEquipment.objects.select_for_update().select_related("instrument").filter(pk=equipment_id).first()
        if row is None or row.removed_at:
            raise ValidationError("Cet équipement n'est plus monté.")
        if row.stock_movement_id:
            raise ValidationError("Cet équipement est déjà sorti du stock.")
        item = StockItem.objects.filter(pk=stock_item_id).first()
        if item is None:
            raise ValidationError("Article introuvable.")
        row.stock_item = item
        row.stock_movement = _take_from_stock(row.instrument, item.uuid, quantity, row.name, user)
        row.updated_by = user
        row.save(update_fields=["stock_item", "stock_movement", "updated_by", "updated_at"])
        return row

    @staticmethod
    @transaction.atomic
    def remove(equipment_id, note="", user=None):
        row = InstrumentEquipment.objects.select_for_update().select_related("instrument").filter(pk=equipment_id).first()
        if row is None or row.removed_at:
            raise ValidationError("Cet équipement n'est plus monté.")
        note = (note or "").strip()[:255]
        row.removed_at = timezone.now()
        row.removal_note = note or "Retiré"
        row.updated_by = user
        row.save(update_fields=["removed_at", "removal_note", "updated_by", "updated_at"])
        _history(row.instrument, "modification", f"{SLOT_LABELS[row.slot]} : pièce retirée", _with_note(row.name, note), user)
        return row

    @staticmethod
    def rows(instrument_id):
        """Current pieces first (by place), then the removed ones, newest first."""
        order = {value: index for index, (value, _) in enumerate(EQUIPMENT_SLOTS)}
        rows = InstrumentEquipment.objects.select_related("stock_item", "stock_movement").filter(instrument_id=instrument_id)
        rows = list(rows)
        current = sorted((r for r in rows if not r.removed_at), key=lambda r: (order[r.slot], r.installed_at))
        removed = sorted((r for r in rows if r.removed_at), key=lambda r: r.removed_at, reverse=True)
        return {
            "current": [EquipmentService._row(r) for r in current],
            "removed": [EquipmentService._row(r) for r in removed],
        }

    @staticmethod
    def _row(row):
        movement = row.stock_movement
        return {
            "id": str(row.uuid),
            "slot": row.slot,
            "slotLabel": SLOT_LABELS.get(row.slot, row.slot),
            "name": row.name,
            "fromOrder": row.from_order,
            "stockItem": str(row.stock_item) if row.stock_item_id else None,
            "cost": float(-movement.quantity * movement.unit_cost) if movement else None,
            "note": row.note,
            "installedAt": row.installed_at.isoformat(),
            "removedAt": row.removed_at.isoformat() if row.removed_at else None,
            "removalNote": row.removal_note,
        }

    @staticmethod
    def public(instrument):
        """What the certificate shows : the pieces mounted now, by place (no cost, no stock)."""
        order = {value: index for index, (value, _) in enumerate(EQUIPMENT_SLOTS)}
        rows = [r for r in instrument.equipment.all() if r.removed_at is None]
        rows.sort(key=lambda r: (order.get(r.slot, 99), r.installed_at))
        return [{"slot": r.slot, "label": SLOT_LABELS.get(r.slot, r.slot), "name": r.name} for r in rows]

