"""Carriers the workshop ships with, and the tracking page of a parcel."""

from urllib.parse import quote

# code : (name shown to the customer, tracking page of a parcel number)
CARRIERS = {
    "colissimo": ("Colissimo", "https://www.laposte.fr/outils/suivre-vos-envois?code={number}"),
    "chronopost": ("Chronopost", "https://www.chronopost.fr/tracking-no-cms/suivi-page?listeNumerosLT={number}"),
    "mondial_relay": ("Mondial Relay", "https://www.mondialrelay.fr/suivi-de-colis/?NumeroExpedition={number}&CodePostal={postal_code}"),
    "dpd": ("DPD", "https://trace.dpd.fr/fr/trace/{number}"),
    "ups": ("UPS", "https://www.ups.com/track?loc=fr_FR&tracknum={number}"),
    "dhl": ("DHL", "https://www.dhl.com/fr-fr/home/tracking.html?tracking-id={number}&submit=1"),
    "fedex": ("FedEx", "https://www.fedex.com/fedextrack/?trknbr={number}"),
    # courier, hand delivery, carrier missing from the list : the tracking link is given by hand
    "other": ("Autre", ""),
}


def carrier_options():
    return [{"value": code, "label": name} for code, (name, _) in CARRIERS.items()]


def tracking_link(order):
    """Tracking page of the parcel : the link given by hand, else the carrier's page for the number."""
    if order.tracking_url:
        return order.tracking_url
    template = CARRIERS.get(order.carrier, ("", ""))[1]
    if not template or not order.tracking_number:
        return ""
    return template.format(number=quote(order.tracking_number.strip()), postal_code=quote(order.postal_code.strip()))


def serialize_shipment(order):
    """Parcel of a shipped order, or None while it has not left."""
    if not order.shipped_at and not order.tracking_number:
        return None
    return {
        "carrier": order.carrier,
        "carrierName": CARRIERS.get(order.carrier, (order.carrier, ""))[0] if order.carrier else "",
        "trackingNumber": order.tracking_number,
        "trackingUrl": tracking_link(order) or None,
        "shippedAt": order.shipped_at.isoformat() if order.shipped_at else None,
    }
