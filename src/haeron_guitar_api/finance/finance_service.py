from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Exists, OuterRef, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from ..models import Order, Payment

ZERO = Decimal("0.00")
# money actually received : a refunded payment was received first, then partly or fully given back
RECEIVED = ["paid", "refunded", "partially_refunded"]


def _bounds(date_from, date_to):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_from, time.min), tz) if date_from else None
    end = timezone.make_aware(datetime.combine(date_to + timedelta(days=1), time.min), tz) if date_to else None
    return start, end


def _in_range(queryset, field, start, end):
    if start:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end:
        queryset = queryset.filter(**{f"{field}__lt": end})
    return queryset


def _money(value):
    return float(value or 0)


def _customer(order):
    return f"{order.first_name} {order.last_name}".strip() or order.email


class FinanceService:
    """Money in and out of the shop, read from the payments : received, refunded, Stripe fees,
    and what customers still owe (orders waiting for their payment)."""

    @staticmethod
    def summary(date_from=None, date_to=None):
        start, end = _bounds(date_from, date_to)
        received = _in_range(Payment.objects.filter(status__in=RECEIVED), "paid_at", start, end)
        refunds = _in_range(Payment.objects.filter(refunded_amount__gt=0), "refunded_at", start, end)

        totals = received.aggregate(amount=Coalesce(Sum("amount"), ZERO), fees=Coalesce(Sum("fee"), ZERO), count=Count("pk"))
        refunded = refunds.aggregate(amount=Coalesce(Sum("refunded_amount"), ZERO))["amount"]

        unpaid = Order.objects.filter(status="pending").order_by("created_at").annotate(
            tried_to_pay=Exists(Payment.objects.filter(order=OuterRef("pk"), provider="stripe"))
        )
        unpaid_totals = unpaid.aggregate(count=Count("pk"), amount=Coalesce(Sum("total_price"), ZERO))

        return {
            "received": _money(totals["amount"]),
            "paymentCount": totals["count"],
            "refunded": _money(refunded),
            "fees": _money(totals["fees"]),
            "net": _money(totals["amount"] - refunded - totals["fees"]),
            "byProvider": {
                row["provider"]: _money(row["amount"])
                for row in received.values("provider").annotate(amount=Sum("amount")).order_by()
            },
            "months": FinanceService._months(received, refunds),
            "unpaid": {
                "count": unpaid_totals["count"],
                "total": _money(unpaid_totals["amount"]),
                "orders": [
                    {
                        "id": str(order.uuid),
                        "reference": str(order.uuid)[:8].upper(),
                        "createdAt": order.created_at.isoformat(),
                        "customer": _customer(order),
                        "email": order.email,
                        "total": _money(order.total_price),
                        # the customer opened the Stripe page but did not pay
                        "triedToPay": order.tried_to_pay,
                    }
                    for order in unpaid[:100]
                ],
            },
            "movements": FinanceService._movements(received, refunds),
        }

    @staticmethod
    def _months(received, refunds):
        months = {}

        def row(month):
            key = month.strftime("%Y-%m")
            return months.setdefault(key, {"month": key, "received": 0.0, "refunded": 0.0, "fees": 0.0})

        for item in received.annotate(month=TruncMonth("paid_at")).values("month").annotate(
            amount=Sum("amount"), fees=Sum("fee")
        ).order_by():
            row(item["month"]).update(received=_money(item["amount"]), fees=_money(item["fees"]))
        for item in refunds.annotate(month=TruncMonth("refunded_at")).values("month").annotate(
            amount=Sum("refunded_amount")
        ).order_by():
            row(item["month"])["refunded"] = _money(item["amount"])
        for month in months.values():
            month["net"] = round(month["received"] - month["refunded"] - month["fees"], 2)
        return sorted(months.values(), key=lambda m: m["month"])

    @staticmethod
    def _movements(received, refunds):
        """Every line of money in or out, newest first : what the accountant needs in the export."""
        movements = []

        def line(payment, kind, date, amount, label):
            order = payment.order
            movements.append(
                {
                    "date": date.isoformat(),
                    "kind": kind,
                    "label": label,
                    "provider": payment.provider,
                    "orderId": str(order.uuid),
                    "reference": str(order.uuid)[:8].upper(),
                    "customer": _customer(order),
                    "amount": _money(amount),
                }
            )

        for payment in received.select_related("order")[:5000]:
            line(payment, "payment", payment.paid_at, payment.amount, "Paiement Stripe" if payment.provider == "stripe" else "Paiement enregistré à la main")
            if payment.fee:
                line(payment, "fee", payment.paid_at, -payment.fee, "Frais Stripe")
        for payment in refunds.select_related("order")[:5000]:
            line(payment, "refund", payment.refunded_at, -payment.refunded_amount, "Remboursement")
        return sorted(movements, key=lambda m: m["date"], reverse=True)
