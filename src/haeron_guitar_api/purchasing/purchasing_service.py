"""Purchases and stock of the parts bought from suppliers.

- A supplier invoice is typed line by line. A line linked to a stock item makes its quantity enter the stock
  (zone "Atelier" or "Vente") at its unit price ; the other lines are plain expenses (tools, shipping, rent...).
- The stock only changes through movements : purchase, use in an instrument, sale of the item alone, transfer between
  the zones, inventory correction. The quantity in a zone is the sum of its movements.
- The cost of an item is the weighted average of what it was bought for (HT) ; a movement out keeps the cost of the
  day, so the cost of an instrument does not change when prices change later.
"""

from collections import defaultdict
from datetime import datetime, time
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from ..models import (
    EXPENSE_CATEGORIES,
    PAYMENT_METHODS,
    STOCK_MOVEMENT_KINDS,
    STOCK_ZONES,
    Instrument,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    StockItem,
    StockMovement,
    Supplier,
)

ZERO = Decimal("0")
CENT = Decimal("0.01")
MAX_FILE_SIZE = 10 * 1024 * 1024
FILE_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
ZONE_LABELS = dict(STOCK_ZONES)
CATEGORY_LABELS = dict(EXPENSE_CATEGORIES)
KIND_LABELS = dict(STOCK_MOVEMENT_KINDS)


def _money(value):
    return float(Decimal(value or 0).quantize(CENT, ROUND_HALF_UP))


def _number(value):
    return float(value or 0)


def _decimal(value, name):
    try:
        return Decimal(str(value))
    except Exception as error:
        raise ValidationError(f"{name} : nombre attendu.") from error


def line_totals(line):
    ht = (line.quantity * line.unit_price_ht).quantize(CENT, ROUND_HALF_UP)
    vat = (ht * line.vat_rate / 100).quantize(CENT, ROUND_HALF_UP)
    return ht, vat


def invoice_totals(lines):
    ht = vat = ZERO
    for line in lines:
        line_ht, line_vat = line_totals(line)
        ht += line_ht
        vat += line_vat
    return {"totalHt": _money(ht), "totalVat": _money(vat), "totalTtc": _money(ht + vat)}


def _invoice_row(invoice):
    lines = list(invoice.lines.all())
    return {
        "id": str(invoice.uuid),
        "supplier": invoice.supplier.name,
        "supplierId": str(invoice.supplier_id),
        "number": invoice.number,
        "issuedOn": invoice.issued_on.isoformat(),
        "dueOn": invoice.due_on.isoformat() if invoice.due_on else None,
        "paidOn": invoice.paid_on.isoformat() if invoice.paid_on else None,
        "paymentMethod": invoice.payment_method,
        "hasFile": bool(invoice.file_name),
        "fileName": invoice.file_name,
        "lineCount": len(lines),
        **invoice_totals(lines),
    }


def average_costs(item_ids=None):
    """Weighted average purchase cost (HT) of each item."""
    purchases = StockMovement.objects.filter(kind="purchase", quantity__gt=0)
    if item_ids is not None:
        purchases = purchases.filter(stock_item_id__in=item_ids)
    totals = defaultdict(lambda: [ZERO, ZERO])
    for movement in purchases.only("stock_item_id", "quantity", "unit_cost"):
        totals[movement.stock_item_id][0] += movement.quantity * movement.unit_cost
        totals[movement.stock_item_id][1] += movement.quantity
    return {item_id: (value / quantity if quantity else ZERO) for item_id, (value, quantity) in totals.items()}


def levels(item_ids=None):
    """Quantity of each item in each zone : {item_id: {"workshop": q, "shop": q}}."""
    movements = StockMovement.objects.all()
    if item_ids is not None:
        movements = movements.filter(stock_item_id__in=item_ids)
    result = defaultdict(lambda: {zone: ZERO for zone, _ in STOCK_ZONES})
    for row in movements.values("stock_item_id", "zone").annotate(quantity=Sum("quantity")).order_by():
        result[row["stock_item_id"]][row["zone"]] = row["quantity"]
    return result


class PurchasingService:
    @staticmethod
    def form_data():
        return {
            "suppliers": [{"id": str(s.uuid), "name": s.name} for s in Supplier.objects.order_by("name")],
            "stockItems": [
                {"id": str(i.uuid), "name": str(i), "family": i.family, "unit": i.unit, "supplierId": str(i.supplier_id or "")}
                for i in StockItem.objects.filter(is_active=True).order_by("family", "name")
            ],
            "categories": [{"value": value, "label": label} for value, label in EXPENSE_CATEGORIES],
            "zones": [{"value": value, "label": label} for value, label in STOCK_ZONES],
            "paymentMethods": [{"value": value, "label": label} for value, label in PAYMENT_METHODS],
        }

    @staticmethod
    def invoices(offset=0, limit=50, search=None, unpaid_only=False):
        queryset = PurchaseInvoice.objects.select_related("supplier").prefetch_related("lines").order_by("-issued_on", "-created_at")
        if search:
            queryset = queryset.filter(
                Q(number__icontains=search) | Q(supplier__name__icontains=search) | Q(lines__designation__icontains=search)
            ).distinct()
        if unpaid_only:
            queryset = queryset.filter(paid_on__isnull=True)
        return {"totalCount": queryset.count(), "results": [_invoice_row(i) for i in queryset[offset : offset + limit]]}

    @staticmethod
    def invoice(invoice_id):
        invoice = (
            PurchaseInvoice.objects.select_related("supplier")
            .prefetch_related("lines__stock_item")
            .defer("file")
            .filter(pk=invoice_id)
            .first()
        )
        if invoice is None:
            return None
        lines = list(invoice.lines.all())
        return {
            **_invoice_row(invoice),
            "notes": invoice.notes,
            "lines": [
                {
                    "id": str(line.uuid),
                    "label": line.designation,
                    "category": line.category,
                    "categoryLabel": CATEGORY_LABELS.get(line.category, line.category),
                    "stockItemId": str(line.stock_item_id) if line.stock_item_id else None,
                    "stockItem": str(line.stock_item) if line.stock_item_id else None,
                    "zone": line.zone,
                    "zoneLabel": ZONE_LABELS.get(line.zone, ""),
                    "quantity": _number(line.quantity),
                    "unitPriceHt": _number(line.unit_price_ht),
                    "vatRate": _number(line.vat_rate),
                    "totalHt": _money(line_totals(line)[0]),
                }
                for line in lines
            ],
        }

    @staticmethod
    @transaction.atomic
    def create_invoice(data, user=None):
        supplier = _supplier(data)
        number = (data.get("number") or "").strip()
        if not number:
            raise ValidationError("Le numéro de facture est obligatoire.")
        if PurchaseInvoice.objects.filter(supplier=supplier, number=number).exists():
            raise ValidationError(f"La facture n° {number} de {supplier.name} est déjà enregistrée.")
        lines = data.get("lines") or []
        if not lines:
            raise ValidationError("Ajoute au moins une ligne.")
        _check_payment(data)

        invoice = PurchaseInvoice.objects.create(
            supplier=supplier,
            number=number,
            issued_on=data["issued_on"],
            due_on=data.get("due_on"),
            paid_on=data.get("paid_on"),
            payment_method=data.get("payment_method") or "",
            notes=data.get("notes") or "",
            created_by=user,
            updated_by=user,
        )
        occurred_at = timezone.make_aware(datetime.combine(invoice.issued_on, time(12)), timezone.get_current_timezone())
        for index, raw in enumerate(lines, start=1):
            line = _line(invoice, raw, index)
            line.save()
            if line.stock_item_id:
                StockMovement.objects.create(
                    stock_item_id=line.stock_item_id,
                    zone=line.zone,
                    kind="purchase",
                    quantity=line.quantity,
                    unit_cost=line.unit_price_ht,
                    invoice_line=line,
                    note=f"Facture {supplier.name} n° {number}",
                    occurred_at=occurred_at,
                    created_by=user,
                    updated_by=user,
                )
        return PurchasingService.invoice(invoice.uuid)

    @staticmethod
    @transaction.atomic
    def update_invoice(invoice_id, data, user=None):
        """Header only : the lines made stock movements, a mistake on a line is fixed by deleting the invoice."""
        invoice = _invoice(invoice_id)
        _check_payment(data)
        for field in ("due_on", "paid_on", "notes"):
            if field in data:
                setattr(invoice, field, data[field] if field != "notes" else (data[field] or ""))
        if "payment_method" in data:
            invoice.payment_method = data["payment_method"] or ""
        if data.get("issued_on"):
            invoice.issued_on = data["issued_on"]
        if data.get("number"):
            invoice.number = data["number"].strip()
        invoice.updated_by = user
        invoice.save()
        return PurchasingService.invoice(invoice.uuid)

    @staticmethod
    @transaction.atomic
    def delete_invoice(invoice_id):
        """Only while what it brought into stock is still there : otherwise the stock would go below zero."""
        invoice = _invoice(invoice_id)
        entries = StockMovement.objects.filter(invoice_line__invoice=invoice)
        current = levels({m.stock_item_id for m in entries})
        for entry in entries.select_related("stock_item"):
            current[entry.stock_item_id][entry.zone] -= entry.quantity
            if current[entry.stock_item_id][entry.zone] < 0:
                raise ValidationError(
                    f"Impossible de supprimer : une partie de « {entry.stock_item} » est déjà sortie du stock. "
                    "Corrige plutôt avec une correction d'inventaire."
                )
        invoice.delete()
        return True

    @staticmethod
    @transaction.atomic
    def attach_file(invoice_id, uploaded):
        if uploaded.size > MAX_FILE_SIZE:
            raise ValidationError("Fichier trop lourd (10 Mo au plus).")
        if uploaded.content_type not in FILE_TYPES:
            raise ValidationError("Formats acceptés : PDF, JPEG, PNG, WebP.")
        invoice = _invoice(invoice_id)
        invoice.file = uploaded.read()
        invoice.file_name = uploaded.name[:255]
        invoice.file_type = uploaded.content_type
        invoice.save(update_fields=["file", "file_name", "file_type", "updated_at"])
        return True

    @staticmethod
    def file(invoice_id):
        invoice = PurchaseInvoice.objects.filter(pk=invoice_id).only("file", "file_name", "file_type").first()
        if invoice is None or not invoice.file_name:
            return None
        return bytes(invoice.file), invoice.file_name, invoice.file_type


def _supplier(data):
    """The chosen supplier, or a new one typed in the invoice form (found again if the name already exists)."""
    if data.get("supplier_id"):
        supplier = Supplier.objects.filter(pk=data["supplier_id"]).first()
        if supplier is None:
            raise ValidationError("Fournisseur introuvable.")
        return supplier
    name = " ".join((data.get("supplier_name") or "").split())
    if not name:
        raise ValidationError("Choisis le fournisseur, ou tape son nom pour le créer.")
    return Supplier.objects.filter(name__iexact=name).first() or Supplier.objects.create(name=name[:150])


def _invoice(invoice_id):
    invoice = PurchaseInvoice.objects.select_for_update().filter(pk=invoice_id).first()
    if invoice is None:
        raise ValidationError("Facture introuvable.")
    return invoice


def _check_payment(data):
    if data.get("payment_method") and data["payment_method"] not in dict(PAYMENT_METHODS):
        raise ValidationError("Moyen de paiement inconnu.")


def _line(invoice, raw, index):
    label = (raw.get("label") or "").strip()
    quantity = _decimal(raw.get("quantity", 1), f"Ligne {index}, quantité")
    unit_price = _decimal(raw.get("unit_price_ht"), f"Ligne {index}, prix unitaire")
    vat_rate = _decimal(raw.get("vat_rate", 20), f"Ligne {index}, TVA")
    category = raw.get("category") or "other"
    if category not in CATEGORY_LABELS:
        raise ValidationError(f"Ligne {index} : catégorie inconnue.")
    if quantity <= 0:
        raise ValidationError(f"Ligne {index} : la quantité doit être positive.")
    if unit_price < 0 or not ZERO <= vat_rate <= 100:
        raise ValidationError(f"Ligne {index} : prix ou TVA invalide.")
    stock_item = None
    zone = ""
    if raw.get("stock_item_id"):
        stock_item = StockItem.objects.filter(pk=raw["stock_item_id"]).first()
        if stock_item is None:
            raise ValidationError(f"Ligne {index} : article introuvable.")
        zone = raw.get("zone") or "workshop"
        if zone not in ZONE_LABELS:
            raise ValidationError(f"Ligne {index} : zone de stock inconnue.")
        label = label or str(stock_item)
    if not label:
        raise ValidationError(f"Ligne {index} : le libellé est obligatoire.")
    return PurchaseInvoiceLine(
        invoice=invoice,
        designation=label,
        category=category,
        stock_item=stock_item,
        zone=zone,
        quantity=quantity,
        unit_price_ht=unit_price,
        vat_rate=vat_rate,
    )


class StockService:
    @staticmethod
    def overview(search=None, family=None, item_ids=None):
        items = StockItem.objects.select_related("supplier").order_by("family", "name")
        if item_ids is not None:
            items = items.filter(pk__in=item_ids)
        if search:
            items = items.filter(Q(name__icontains=search) | Q(reference__icontains=search) | Q(family__icontains=search))
        if family:
            items = items.filter(family=family)
        items = list(items)
        ids = [i.uuid for i in items]
        quantities = levels(ids)
        costs = average_costs(ids)
        rows = []
        totals = {zone: ZERO for zone, _ in STOCK_ZONES}
        for item in items:
            by_zone = quantities[item.uuid]
            quantity = sum(by_zone.values(), ZERO)
            cost = costs.get(item.uuid, ZERO)
            for zone in totals:
                totals[zone] += by_zone[zone] * cost
            rows.append(
                {
                    "id": str(item.uuid),
                    "name": item.name,
                    "reference": item.reference,
                    "family": item.family,
                    "supplier": item.supplier.name if item.supplier_id else "",
                    "unit": item.unit,
                    "isActive": item.is_active,
                    "workshop": _number(by_zone["workshop"]),
                    "shop": _number(by_zone["shop"]),
                    "quantity": _number(quantity),
                    "averageCost": _number(cost.quantize(Decimal("0.0001"))),
                    "value": _money(quantity * cost),
                    "low": quantity <= item.alert_quantity and item.alert_quantity > 0,
                }
            )
        return {
            "items": rows,
            "families": sorted({i.family for i in StockItem.objects.exclude(family="")}),
            "value": {zone: _money(value) for zone, value in totals.items()} | {"total": _money(sum(totals.values(), ZERO))},
            "kinds": [{"value": v, "label": l} for v, l in STOCK_MOVEMENT_KINDS if v != "purchase"],
            "zones": [{"value": v, "label": l} for v, l in STOCK_ZONES],
        }

    @staticmethod
    def item_sheet(item_id):
        item = StockItem.objects.select_related("supplier").filter(pk=item_id).first()
        if item is None:
            return None
        row = StockService.overview(item_ids=[item.uuid])["items"][0]
        movements = (
            StockMovement.objects.filter(stock_item=item)
            .select_related("instrument__master_part", "order", "invoice_line__invoice", "created_by")
            .order_by("-occurred_at", "-created_at")[:500]
        )
        return {
            **row,
            "notes": item.notes,
            "alertQuantity": _number(item.alert_quantity),
            "movements": [
                {
                    "id": str(m.uuid),
                    "occurredAt": m.occurred_at.isoformat(),
                    "kind": m.kind,
                    "kindLabel": KIND_LABELS.get(m.kind, m.kind),
                    "zone": m.zone,
                    "zoneLabel": ZONE_LABELS.get(m.zone, m.zone),
                    "quantity": _number(m.quantity),
                    "unitCost": _number(m.unit_cost),
                    "note": m.note,
                    "invoiceId": str(m.invoice_line.invoice_id) if m.invoice_line_id else None,
                    "instrumentId": str(m.instrument_id) if m.instrument_id else None,
                    "instrument": m.instrument.master_part.serial_number if m.instrument_id else None,
                    "orderId": str(m.order.uuid) if m.order_id else None,
                    "by": m.created_by.email if m.created_by_id else "",
                }
                for m in movements
            ],
        }

    @staticmethod
    @transaction.atomic
    def move(data, user=None):
        """use / sale : out of a zone ; transfer : from a zone to the other ; adjustment : + or - (inventory)."""
        item = StockItem.objects.select_for_update().filter(pk=data.get("stock_item_id")).first()
        if item is None:
            raise ValidationError("Article introuvable.")
        kind = data.get("kind")
        zone = data.get("zone") or "workshop"
        if kind not in KIND_LABELS or kind == "purchase":
            raise ValidationError("Type de mouvement inconnu (les achats passent par une facture).")
        if zone not in ZONE_LABELS:
            raise ValidationError("Zone de stock inconnue.")
        quantity = _decimal(data.get("quantity"), "Quantité")
        if quantity == 0 or (kind != "adjustment" and quantity < 0):
            raise ValidationError("La quantité doit être positive.")

        instrument = None
        if data.get("instrument_id"):
            instrument = Instrument.objects.filter(pk=data["instrument_id"]).first()
            if instrument is None:
                raise ValidationError("Instrument introuvable.")
        if kind == "use" and instrument is None:
            raise ValidationError("Choisis l'instrument dans lequel l'article est monté.")

        available = levels([item.uuid])[item.uuid][zone]
        out = quantity if kind != "adjustment" else -quantity
        if out > available:
            raise ValidationError(
                f"Stock insuffisant en {ZONE_LABELS[zone]} : {_number(available)} {item.unit} disponible(s)."
            )
        cost = average_costs([item.uuid]).get(item.uuid, ZERO)
        common = {
            "stock_item": item,
            "kind": kind,
            "unit_cost": cost,
            "note": (data.get("note") or "")[:255],
            "occurred_at": timezone.now(),
            "created_by": user,
            "updated_by": user,
        }
        if kind == "transfer":
            to_zone = "shop" if zone == "workshop" else "workshop"
            StockMovement.objects.create(zone=zone, quantity=-quantity, **common)
            StockMovement.objects.create(zone=to_zone, quantity=quantity, **common)
        else:
            StockMovement.objects.create(zone=zone, quantity=-out, instrument=instrument, **common)
        return StockService.item_sheet(item.uuid)

    @staticmethod
    def instrument_cost(instrument_id):
        """External parts mounted on an instrument and what they cost (HT, at the time they were mounted)."""
        rows = []
        total = ZERO
        for m in StockMovement.objects.filter(instrument_id=instrument_id, kind="use").select_related("stock_item"):
            cost = -m.quantity * m.unit_cost
            total += cost
            rows.append({"item": str(m.stock_item), "quantity": _number(-m.quantity), "cost": _money(cost)})
        return {"parts": rows, "total": _money(total)}


def expenses(start=None, end=None):
    """Supplier invoices issued in the period, by category (for the finances page)."""
    lines = PurchaseInvoiceLine.objects.select_related("invoice__supplier")
    if start:
        lines = lines.filter(invoice__issued_on__gte=start)
    if end:
        lines = lines.filter(invoice__issued_on__lt=end)
    by_category = defaultdict(lambda: [ZERO, ZERO])
    by_month = defaultdict(lambda: ZERO)
    by_invoice = {}
    for line in lines:
        ht, vat = line_totals(line)
        by_category[line.category][0] += ht
        by_category[line.category][1] += vat
        by_month[line.invoice.issued_on.strftime("%Y-%m")] += ht + vat
        entry = by_invoice.setdefault(line.invoice_id, {"invoice": line.invoice, "ttc": ZERO})
        entry["ttc"] += ht + vat
    total_ht = sum((v[0] for v in by_category.values()), ZERO)
    total_vat = sum((v[1] for v in by_category.values()), ZERO)
    return {
        "totalHt": _money(total_ht),
        "totalVat": _money(total_vat),
        "totalTtc": _money(total_ht + total_vat),
        "byCategory": sorted(
            (
                {"category": c, "label": CATEGORY_LABELS.get(c, c), "ht": _money(v[0]), "ttc": _money(v[0] + v[1])}
                for c, v in by_category.items()
            ),
            key=lambda row: -row["ttc"],
        ),
        "byMonth": {month: _money(value) for month, value in by_month.items()},
        "invoices": [
            {
                "date": e["invoice"].issued_on.isoformat(),
                "id": str(e["invoice"].uuid),
                "supplier": e["invoice"].supplier.name,
                "number": e["invoice"].number,
                "ttc": _money(e["ttc"]),
            }
            for e in by_invoice.values()
        ],
    }


def to_pay():
    """Supplier invoices not paid yet."""
    invoices = PurchaseInvoice.objects.filter(paid_on__isnull=True).select_related("supplier").prefetch_related("lines").defer("file")
    rows = [_invoice_row(i) for i in invoices.order_by("due_on", "issued_on")]
    return {"count": len(rows), "total": _money(sum(Decimal(str(r["totalTtc"])) for r in rows)), "invoices": rows[:100]}
