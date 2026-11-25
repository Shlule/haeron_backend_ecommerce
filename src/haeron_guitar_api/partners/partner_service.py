"""Business partners : a code (typed at checkout or carried by a link ?ref=CODE) gives the customer a discount,
and the partner earns a commission on what the customer paid.

The discount and the rates are copied on the order at checkout : changing a partner only changes the next orders.
The commission of an order is worked out from its payments, so a refund lowers it on its own and a cancelled order
earns nothing. The money sent to the partner is recorded as payouts : what is due is earned minus paid out.
The shop is not subject to VAT (art. 293 B du CGI) : amounts are what the customer paid."""

import re
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from decouple import config
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from ..models import PAYMENT_METHODS, Order, Partner, PartnerPayout, Payment

SHOP_URL = config("SHOP_URL", default="http://localhost:3000").rstrip("/")
ZERO = Decimal("0.00")
CENT = Decimal("0.01")
# above this, commissions paid to one partner in a calendar year go on the DAS2 (fees paid to third parties)
DAS2_THRESHOLD = Decimal("1200")
# orders whose money is kept : a pending order is not paid yet, a cancelled one earns nothing
EARNING_STATUSES = ("paid", "processing", "shipped", "completed")
RECEIVED = ("paid", "refunded", "partially_refunded")
CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{3,40}$")
METHOD_LABELS = dict(PAYMENT_METHODS)


def normalize_code(code):
    return "".join((code or "").split()).upper()


def _money(value):
    return float(value or 0)


def _round(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def link(partner):
    """Link to give the partner : any shop page works, the code is kept by the shop for 30 days."""
    return f"{SHOP_URL}/?ref={partner.code}"


def find_valid(code, day=None):
    """The active partner of this code, or None (unknown, switched off or past its last day)."""
    code = normalize_code(code)
    if not code:
        return None
    partner = Partner.objects.filter(code=code, is_active=True).first()
    if partner is None:
        return None
    day = day or timezone.localdate()
    if partner.valid_until and partner.valid_until < day:
        return None
    return partner


def public_code(code):
    """What the shop may show about a code : nothing about the partner but its discount."""
    partner = find_valid(code)
    if partner is None:
        return None
    return {"code": partner.code, "discountPercent": _money(partner.discount_percent)}


def apply_to_order(order, code, subtotal):
    """Checkout : the discount of the code on the cart total, and the partner kept on the order.
    Returns the total to pay. An invalid code is refused rather than silently ignored."""
    if not normalize_code(code):
        return subtotal
    partner = find_valid(code)
    if partner is None:
        raise ValidationError("Ce code partenaire n'est pas valide (ou n'est plus actif).")
    discount = min(_round(subtotal * partner.discount_percent / 100), subtotal)
    order.partner = partner
    order.partner_code = partner.code
    order.discount_percent = partner.discount_percent
    order.discount_amount = discount
    order.commission_percent = partner.commission_percent
    return subtotal - discount


def _kept(order):
    """Money of the order kept by the shop : paid, minus what was refunded. Payments must be prefetched."""
    if order.status not in EARNING_STATUSES:
        return ZERO
    return sum(
        (p.amount - p.refunded_amount for p in order.payments.all() if p.status in RECEIVED), ZERO
    )


def _paid_at(order):
    dates = [p.paid_at for p in order.payments.all() if p.status in RECEIVED and p.paid_at]
    return min(dates) if dates else order.created_at


def _order_row(order):
    kept = _kept(order)
    return {
        "id": str(order.uuid),
        "reference": str(order.uuid)[:8].upper(),
        "status": order.status,
        "createdAt": order.created_at.isoformat(),
        "paidAt": _paid_at(order).isoformat(),
        "customer": f"{order.first_name} {order.last_name}".strip() or order.email,
        "total": _money(order.total_price),
        "discount": _money(order.discount_amount),
        "kept": _money(kept),
        "commissionPercent": _money(order.commission_percent),
        "commission": _money(_round(kept * order.commission_percent / 100)),
    }


def _orders(partner_ids):
    payments = Prefetch("payments", queryset=Payment.objects.order_by("created_at"))
    return Order.objects.filter(partner_id__in=partner_ids).prefetch_related(payments).order_by("-created_at")


def _payout_row(payout):
    return {
        "id": str(payout.uuid),
        "amount": _money(payout.amount),
        "paidOn": payout.paid_on.isoformat(),
        "paymentMethod": payout.payment_method,
        "paymentMethodLabel": METHOD_LABELS.get(payout.payment_method, ""),
        "note": payout.note,
    }


def _partner_row(partner, orders, payouts):
    rows = [_order_row(order) for order in orders]
    earning = [row for row in rows if row["status"] in EARNING_STATUSES]
    earned = sum((Decimal(str(row["commission"])) for row in earning), ZERO)
    paid_out = sum((payout.amount for payout in payouts), ZERO)
    today = timezone.localdate()
    return {
        "id": str(partner.uuid),
        "name": partner.name,
        "email": partner.email,
        "phone": partner.phone,
        "company": partner.company,
        "siret": partner.siret,
        "address": partner.address,
        "code": partner.code,
        "link": link(partner),
        "discountPercent": _money(partner.discount_percent),
        "commissionPercent": _money(partner.commission_percent),
        "isActive": partner.is_active,
        "validUntil": partner.valid_until.isoformat() if partner.valid_until else None,
        # the code works today on the shop
        "usable": partner.is_active and not (partner.valid_until and partner.valid_until < today),
        "notes": partner.notes,
        "createdAt": partner.created_at.isoformat(),
        "orderCount": len(earning),
        "sales": _money(sum((Decimal(str(row["kept"])) for row in earning), ZERO)),
        "discounts": _money(sum((Decimal(str(row["discount"])) for row in earning), ZERO)),
        "earned": _money(earned),
        "paidOut": _money(paid_out),
        "due": _money(earned - paid_out),
        "_rows": rows,
    }


class PartnerService:
    @staticmethod
    def list():
        partners = list(Partner.objects.order_by("-is_active", "name"))
        ids = [p.pk for p in partners]
        orders, payouts = defaultdict(list), defaultdict(list)
        for order in _orders(ids):
            orders[order.partner_id].append(order)
        for payout in PartnerPayout.objects.filter(partner_id__in=ids):
            payouts[payout.partner_id].append(payout)
        rows = []
        for partner in partners:
            row = _partner_row(partner, orders[partner.pk], payouts[partner.pk])
            row.pop("_rows")
            rows.append(row)
        return {
            "results": rows,
            "totals": {
                key: round(sum(row[key] for row in rows), 2) for key in ("sales", "discounts", "earned", "paidOut", "due")
            },
            "shopUrl": SHOP_URL,
            "paymentMethods": [{"value": v, "label": label} for v, label in PAYMENT_METHODS],
        }

    @staticmethod
    def detail(partner_id):
        partner = Partner.objects.filter(pk=partner_id).first()
        if partner is None:
            return None
        payouts = list(partner.payouts.order_by("-paid_on", "-created_at"))
        row = _partner_row(partner, list(_orders([partner.pk])), payouts)
        orders = row.pop("_rows")

        # monthly statement : commissions earned by month of payment, payouts by month sent
        months = defaultdict(lambda: {"orders": 0, "sales": ZERO, "earned": ZERO, "paidOut": ZERO})
        years = defaultdict(lambda: {"earned": ZERO, "paidOut": ZERO})
        for order in orders:
            if order["status"] not in EARNING_STATUSES:
                continue
            month = months[order["paidAt"][:7]]
            month["orders"] += 1
            month["sales"] += Decimal(str(order["kept"]))
            month["earned"] += Decimal(str(order["commission"]))
            years[order["paidAt"][:4]]["earned"] += Decimal(str(order["commission"]))
        for payout in payouts:
            months[payout.paid_on.strftime("%Y-%m")]["paidOut"] += payout.amount
            years[str(payout.paid_on.year)]["paidOut"] += payout.amount
        return {
            **row,
            "orders": orders,
            "payouts": [_payout_row(p) for p in payouts],
            "months": [
                {"month": key, "orders": m["orders"], "sales": _money(m["sales"]), "earned": _money(m["earned"]),
                 "paidOut": _money(m["paidOut"])}
                for key, m in sorted(months.items(), reverse=True)
            ],
            # DAS2 : commissions paid in the year above 1 200 euros are declared (identity, address, amount)
            "years": [
                {"year": key, "earned": _money(y["earned"]), "paidOut": _money(y["paidOut"]),
                 "das2": y["paidOut"] > DAS2_THRESHOLD}
                for key, y in sorted(years.items(), reverse=True)
            ],
            "das2Threshold": _money(DAS2_THRESHOLD),
            "paymentMethods": [{"value": v, "label": label} for v, label in PAYMENT_METHODS],
        }

    @staticmethod
    @transaction.atomic
    def save(data, partner_id=None):
        partner = Partner() if partner_id is None else Partner.objects.select_for_update().filter(pk=partner_id).first()
        if partner is None:
            raise ValidationError("Partenaire introuvable.")
        name = " ".join((data.get("name") or "").split())
        if not name:
            raise ValidationError("Indique le nom du partenaire.")
        code = normalize_code(data.get("code"))
        if not CODE_PATTERN.match(code):
            raise ValidationError("Le code doit faire 3 à 40 caractères : lettres, chiffres, - ou _ (sans espace ni accent).")
        if Partner.objects.filter(code=code).exclude(pk=partner.pk).exists():
            raise ValidationError(f"Le code {code} est déjà pris par un autre partenaire.")
        discount = Decimal(str(data.get("discount_percent") or 0))
        commission = Decimal(str(data.get("commission_percent") or 0))
        if not ZERO <= discount < 100:
            raise ValidationError("La réduction doit être comprise entre 0 et 99 %.")
        if not ZERO <= commission <= 100:
            raise ValidationError("La commission doit être comprise entre 0 et 100 %.")
        # changing the code : past orders keep the old one, the old link stops working
        partner.name = name[:150]
        partner.code = code
        partner.discount_percent = discount
        partner.commission_percent = commission
        partner.is_active = bool(data.get("is_active", True))
        partner.valid_until = data.get("valid_until")
        for field, size in (("email", 254), ("phone", 30), ("company", 150), ("siret", 20), ("address", 255)):
            setattr(partner, field, (data.get(field) or "").strip()[:size])
        partner.notes = data.get("notes") or ""
        partner.save()
        return PartnerService.detail(partner.pk)

    @staticmethod
    def delete(partner_id):
        partner = Partner.objects.filter(pk=partner_id).first()
        if partner is None:
            raise ValidationError("Partenaire introuvable.")
        if partner.orders.exists() or partner.payouts.exists():
            raise ValidationError("Ce partenaire a déjà des commandes ou des versements : désactive-le plutôt.")
        partner.delete()
        return True

    @staticmethod
    def record_payout(partner_id, data, user=None):
        partner = Partner.objects.filter(pk=partner_id).first()
        if partner is None:
            raise ValidationError("Partenaire introuvable.")
        amount = Decimal(str(data.get("amount") or 0))
        if amount <= 0:
            raise ValidationError("Le montant versé doit être positif.")
        method = data.get("payment_method") or ""
        if method and method not in METHOD_LABELS:
            raise ValidationError("Moyen de paiement inconnu.")
        PartnerPayout.objects.create(
            partner=partner,
            amount=_round(amount),
            paid_on=data.get("paid_on") or timezone.localdate(),
            payment_method=method,
            note=(data.get("note") or "").strip()[:255],
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
        return PartnerService.detail(partner.pk)

    @staticmethod
    def delete_payout(payout_id):
        payout = PartnerPayout.objects.filter(pk=payout_id).first()
        if payout is None:
            raise ValidationError("Versement introuvable.")
        partner_id = payout.partner_id
        payout.delete()
        return PartnerService.detail(partner_id)


def payouts(start=None, end=None):
    """Commissions sent to partners in the period (end excluded) : an expense of the finances page."""
    queryset = PartnerPayout.objects.select_related("partner").order_by("paid_on")
    if start:
        queryset = queryset.filter(paid_on__gte=start)
    if end:
        queryset = queryset.filter(paid_on__lt=end)
    return list(queryset)
