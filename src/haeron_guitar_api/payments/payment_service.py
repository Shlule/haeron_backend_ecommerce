import logging
from decimal import Decimal

import stripe
from decouple import config
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import Order, Payment

logger = logging.getLogger(__name__)

# where Stripe sends the customer back : the order confirmation page of the shop
SHOP_URL = config("SHOP_URL", default="http://localhost:3000").rstrip("/")


def _cents(amount):
    return int((Decimal(amount) * 100).quantize(Decimal(1)))


def _euros(cents):
    return (Decimal(cents or 0) / 100).quantize(Decimal("0.01"))


def _get(obj, key, default=None):
    # Stripe objects and plain dicts (tests, webhook payloads) are read the same way
    try:
        value = obj[key]
    except (KeyError, TypeError, AttributeError):
        return default
    return default if value is None else value


class PaymentService:
    """Payment of an order with Stripe Checkout (Stripe hosts the card page), plus the payments recorded by hand.
    The order becomes "paid" only once Stripe says so : by the webhook, or when the customer comes back
    and the session is read again from Stripe (never from what the browser says)."""

    @staticmethod
    def start_checkout(order_uuid):
        """Creates a Stripe Checkout session for a pending order and returns the Stripe page url."""
        order = Order.objects.prefetch_related("order_items").filter(uuid=order_uuid).first()
        if order is None:
            raise ValidationError("Commande introuvable.")
        if order.status != "pending":
            raise ValidationError("Cette commande est déjà payée." if order.status != "cancelled" else "Cette commande est annulée.")
        items = list(order.order_items.order_by("pk"))
        if not items or not order.total_price:
            raise ValidationError("Cette commande n'a rien à payer.")

        order_id = str(order.uuid)
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "quantity": item.quantity,
                    "price_data": {
                        "currency": "eur",
                        "unit_amount": _cents(item.unit_price),
                        "product_data": {"name": item.product_name},
                    },
                }
                for item in items
            ],
            customer_email=order.email or None,
            client_reference_id=order_id,
            metadata={"order_id": order_id},
            payment_intent_data={"metadata": {"order_id": order_id}},
            success_url=f"{SHOP_URL}/commande/{order_id}?paiement=ok&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{SHOP_URL}/commande/{order_id}?paiement=annule",
            locale="fr",
        )
        Payment.objects.create(
            order=order,
            provider="stripe",
            amount=_euros(_get(session, "amount_total")) if _get(session, "amount_total") else order.total_price,
            stripe_session_id=_get(session, "id"),
            livemode=bool(_get(session, "livemode", False)),
        )
        return _get(session, "url")

    @staticmethod
    def confirm_checkout(order_uuid, session_id):
        """Customer back from Stripe : reads the session from Stripe and records the payment if it is paid.
        Same result as the webhook, useful when the webhook is late or not set up (local tests)."""
        payment = Payment.objects.filter(stripe_session_id=session_id, order__uuid=order_uuid).first()
        if payment is None:
            raise ValidationError("Paiement introuvable.")
        session = stripe.checkout.Session.retrieve(session_id)
        PaymentService.apply_session(session)
        from ..storefront.storefront_service import StorefrontService  # avoids a circular import

        return StorefrontService.find_order(order_uuid)

    # --- events from Stripe (webhook) ---

    @staticmethod
    def handle_event(event):
        kind = _get(event, "type")
        obj = _get(_get(event, "data", {}), "object", {})
        if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            PaymentService.apply_session(obj)
        elif kind == "checkout.session.async_payment_failed":
            Payment.objects.filter(stripe_session_id=_get(obj, "id"), status="pending").update(status="failed")
        elif kind == "checkout.session.expired":
            Payment.objects.filter(stripe_session_id=_get(obj, "id"), status="pending").update(status="expired")
        elif kind == "charge.refunded":
            PaymentService.apply_refund(obj)

    @staticmethod
    def apply_session(session):
        """Records a paid Checkout session. Safe to call several times (webhook + customer return)."""
        if _get(session, "payment_status") != "paid":
            return None
        with transaction.atomic():
            payment = Payment.objects.select_for_update().filter(stripe_session_id=_get(session, "id")).first()
            if payment is None:
                # session made outside this backend : find the order by its metadata
                order_id = _get(_get(session, "metadata", {}), "order_id")
                order = Order.objects.filter(uuid=order_id).first() if order_id else None
                if order is None:
                    logger.warning("Stripe session %s paid for an unknown order", _get(session, "id"))
                    return None
                payment = Payment(order=order, provider="stripe", stripe_session_id=_get(session, "id"))
            if payment.status == "paid" or payment.status.endswith("refunded"):
                return payment
            payment.status = "paid"
            payment.amount = _euros(_get(session, "amount_total")) if _get(session, "amount_total") else payment.amount
            payment.currency = _get(session, "currency", "eur")
            payment.stripe_payment_intent_id = _get(session, "payment_intent", "") or ""
            payment.livemode = bool(_get(session, "livemode", False))
            payment.paid_at = timezone.now()
            payment.save()
            # a pending order becomes paid ; an order already in production keeps its status
            Order.objects.filter(pk=payment.order_id, status="pending").update(status="paid")
        PaymentService._store_fee(payment)
        return payment

    @staticmethod
    def _store_fee(payment):
        # Stripe fee of the charge : money going out, shown in the back-office finances
        if not payment.stripe_payment_intent_id:
            return
        try:
            intent = stripe.PaymentIntent.retrieve(
                payment.stripe_payment_intent_id, expand=["latest_charge.balance_transaction"]
            )
            fee = _get(_get(_get(intent, "latest_charge", {}), "balance_transaction", {}), "fee")
            if fee is not None:
                Payment.objects.filter(pk=payment.pk).update(fee=_euros(fee))
        except Exception:  # the fee is a nice to have : never fail a payment for it
            logger.exception("Could not read the Stripe fee of %s", payment.stripe_payment_intent_id)

    @staticmethod
    def apply_refund(charge):
        payment = Payment.objects.filter(stripe_payment_intent_id=_get(charge, "payment_intent") or "-").first()
        if payment is None:
            return None
        refunded = _euros(_get(charge, "amount_refunded", 0))
        payment.refunded_amount = refunded
        payment.status = "refunded" if refunded >= payment.amount else "partially_refunded"
        payment.refunded_at = timezone.now()
        payment.save(update_fields=["refunded_amount", "status", "refunded_at"])
        return payment

    # --- payments recorded by hand ---

    @staticmethod
    def record_manual(order):
        """Order marked as paid in the back-office (transfer, cash...) : keeps the money in the finances."""
        if order.payments.filter(status__in=["paid", "partially_refunded"]).exists():
            return None
        return Payment.objects.create(
            order=order,
            provider="manual",
            status="paid",
            amount=order.total_price or 0,
            paid_at=timezone.now(),
        )

    @staticmethod
    def serialize(payment):
        return {
            "id": str(payment.uuid),
            "provider": payment.provider,
            "status": payment.status,
            "amount": float(payment.amount),
            "fee": float(payment.fee) if payment.fee is not None else None,
            "refundedAmount": float(payment.refunded_amount),
            "createdAt": payment.created_at.isoformat(),
            "paidAt": payment.paid_at.isoformat() if payment.paid_at else None,
            "refundedAt": payment.refunded_at.isoformat() if payment.refunded_at else None,
            "stripeUrl": (
                f"https://dashboard.stripe.com/{'' if payment.livemode else 'test/'}payments/{payment.stripe_payment_intent_id}"
                if payment.stripe_payment_intent_id
                else None
            ),
        }
