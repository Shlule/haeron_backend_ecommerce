"""E-mails sent to the customer as the order moves on : payment confirmed, parcel shipped.
Each one links to the order page of the shop, which shows the status and the parcel tracking.
An e-mail never blocks the order : a failure is logged and the payment or the shipment stays recorded."""

import logging
from zoneinfo import ZoneInfo

from decouple import config
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.html import escape

from ..models import Order, OrderItem
from .item_summary import summarize
from .shipping import CARRIERS, tracking_link

logger = logging.getLogger(__name__)

SHOP_URL = config("SHOP_URL", default="http://localhost:3000").rstrip("/")

COUNTRIES = {"FR": "France", "BE": "Belgique", "CH": "Suisse", "LU": "Luxembourg", "DE": "Allemagne",
             "ES": "Espagne", "IT": "Italie", "GB": "Royaume-Uni"}


def order_link(order):
    return f"{SHOP_URL}/commande/{order.uuid}"


def _terms_line(order):
    """The CGV accepted at checkout, sent with the confirmation so the customer keeps them."""
    if not order.terms_accepted_at:
        return f"Conditions générales de vente : {SHOP_URL}/cgv"
    # French time for the customer (the server works in UTC)
    day = timezone.localtime(order.terms_accepted_at, ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y à %H:%M")
    return f"Conditions générales de vente acceptées le {day} : {SHOP_URL}/cgv"


def _euros(amount):
    return f"{amount:.2f}".replace(".", ",") + " €"


def _button(label, url):
    return (
        f'<p style="margin:28px 0"><a href="{escape(url)}" style="display:inline-block;padding:12px 26px;'
        f'background:#111;color:#fff;border-radius:999px;text-decoration:none;font-weight:600">{escape(label)}</a></p>'
    )


def _layout(title, body):
    return (
        '<div style="background:#f4f2ef;padding:32px 12px;font-family:Helvetica,Arial,sans-serif;color:#111">'
        '<div style="max-width:560px;margin:0 auto;background:#fff;border-radius:16px;padding:32px">'
        '<p style="margin:0 0 24px;font-size:12px;letter-spacing:.25em;text-transform:uppercase;color:#888">Haeron Guitar</p>'
        f'<h1 style="margin:0 0 16px;font-size:24px;font-weight:600">{escape(title)}</h1>'
        f"{body}"
        '<p style="margin:32px 0 0;font-size:14px;color:#666">À bientôt,<br>L\'équipe Haeron Guitar</p>'
        "</div></div>"
    )


class OrderEmails:
    @staticmethod
    def after_commit(send, order_id):
        """Sends once the change is saved (an e-mail about a rolled back payment would be wrong)."""
        transaction.on_commit(lambda: OrderEmails._safely(send, order_id))

    @staticmethod
    def _safely(send, order_id):
        order = (
            Order.objects.prefetch_related(Prefetch("order_items", queryset=OrderItem.objects.order_by("pk")))
            .filter(pk=order_id)
            .first()
        )
        if order is None or not order.email:
            return
        try:
            send(order)
        except Exception:  # SMTP down, bad address... : the order itself is fine
            logger.exception("E-mail %s of order %s not sent", send.__name__, order.uuid)

    @staticmethod
    def _greeting(order):
        return f"Bonjour {order.first_name}" if order.first_name else "Bonjour"

    @staticmethod
    def _reference(order):
        return str(order.uuid)[:8].upper()

    @staticmethod
    def confirmation(order):
        """Order paid (Stripe, or recorded by hand in the back-office) : what was ordered and where it goes."""
        reference = OrderEmails._reference(order)
        greeting = OrderEmails._greeting(order)
        items = list(order.order_items.all())
        total = _euros(order.total_price or 0)
        link = order_link(order)
        address = [
            f"{order.first_name} {order.last_name}".strip(),
            order.address,
            f"{order.postal_code} {order.city}".strip(),
            COUNTRIES.get(order.country, order.country),
        ]
        address = [line for line in address if line]

        text_items = []
        for item in items:
            quantity = f" × {item.quantity}" if item.quantity > 1 else ""
            text_items.append(f"- {item.product_name}{quantity} : {_euros(item.unit_price * item.quantity)}")
            text_items += [f"    {line}" for line in summarize((item.config_snapshot or {}).get("options"))]
        text = (
            f"{greeting},\n\n"
            f"Merci pour votre commande ! Nous avons bien reçu votre paiement de {total}.\n\n"
            f"Commande {reference}\n" + "\n".join(text_items) + f"\nTotal : {total}\n\n"
            "Livraison :\n" + "\n".join(address) + "\n\n"
            "Nous préparons votre commande et vous écrirons dès qu'elle sera expédiée, avec le numéro de suivi du colis.\n"
            f"Suivre votre commande : {link}\n\n"
            f"{_terms_line(order)}\n\n"
            "Haeron Guitar"
        )

        rows = "".join(
            '<tr><td style="padding:12px 0;border-top:1px solid #eee;vertical-align:top">'
            f'<strong>{escape(item.product_name)}</strong>'
            + (f' <span style="color:#888">× {item.quantity}</span>' if item.quantity > 1 else "")
            + "".join(
                f'<div style="font-size:13px;color:#666;margin-top:4px">{escape(line)}</div>'
                for line in summarize((item.config_snapshot or {}).get("options"))
            )
            + '</td><td style="padding:12px 0 12px 16px;border-top:1px solid #eee;vertical-align:top;text-align:right;'
            f'white-space:nowrap">{_euros(item.unit_price * item.quantity)}</td></tr>'
            for item in items
        )
        html = _layout(
            "Merci pour votre commande !",
            f"<p>{escape(greeting)},</p>"
            f"<p>Nous avons bien reçu votre paiement. Votre commande <strong>{reference}</strong> est confirmée.</p>"
            f'<table style="width:100%;border-collapse:collapse;margin-top:24px;font-size:15px">{rows}'
            '<tr><td style="padding:12px 0;border-top:2px solid #111"><strong>Total</strong></td>'
            f'<td style="padding:12px 0;border-top:2px solid #111;text-align:right"><strong>{total}</strong></td></tr></table>'
            '<p style="margin:24px 0 4px;font-size:12px;letter-spacing:.2em;text-transform:uppercase;color:#888">Livraison</p>'
            f'<p style="margin:0;line-height:1.5">{"<br>".join(escape(line) for line in address)}</p>'
            "<p>Nous préparons votre commande et vous écrirons dès qu'elle sera expédiée, "
            "avec le numéro de suivi du colis.</p>" + _button("Suivre ma commande", link)
            + f'<p style="font-size:12px;color:#888">{escape(_terms_line(order))}</p>',
        )
        send_mail(f"Haeron Guitar : commande {reference} confirmée", text, settings.DEFAULT_FROM_EMAIL, [order.email],
                  html_message=html)
        logger.info("Confirmation of order %s sent", reference)

    @staticmethod
    def shipped(order):
        """Parcel handed to the carrier : its number and the link to follow it."""
        reference = OrderEmails._reference(order)
        greeting = OrderEmails._greeting(order)
        carrier = CARRIERS.get(order.carrier, ("", ""))[0] if order.carrier not in ("", "other") else ""
        tracking = tracking_link(order)
        link = order_link(order)

        parcel = []
        if carrier:
            parcel.append(f"Transporteur : {carrier}")
        if order.tracking_number:
            parcel.append(f"Numéro de suivi : {order.tracking_number}")
        text = (
            f"{greeting},\n\n"
            f"Bonne nouvelle : votre commande {reference} est expédiée.\n\n"
            + ("\n".join(parcel) + "\n" if parcel else "")
            + (f"Suivre le colis : {tracking}\n" if tracking else "")
            + f"Votre commande : {link}\n\nHaeron Guitar"
        )
        html = _layout(
            "Votre commande est expédiée",
            f"<p>{escape(greeting)},</p>"
            f"<p>Bonne nouvelle : votre commande <strong>{reference}</strong> a quitté notre atelier.</p>"
            + (
                '<p style="margin:20px 0;padding:16px;background:#f7f7f7;border-radius:12px;line-height:1.6">'
                + "<br>".join(escape(line) for line in parcel)
                + "</p>"
                if parcel
                else ""
            )
            + (_button("Suivre mon colis", tracking) + f'<p style="font-size:14px"><a href="{escape(link)}" '
               'style="color:#111">Voir ma commande</a></p>' if tracking else _button("Voir ma commande", link)),
        )
        send_mail(f"Haeron Guitar : votre commande {reference} est expédiée", text, settings.DEFAULT_FROM_EMAIL,
                  [order.email], html_message=html)
        logger.info("Shipping e-mail of order %s sent", reference)
