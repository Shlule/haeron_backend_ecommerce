"""Link between what was sold (an order line) and what the workshop delivers for it.

The order line keeps its snapshot of what was sold, for good. An instrument, or a piece sold alone,
points to the order line it was made or taken from stock for (Instrument.order_item, Part.order_item).
A line of quantity 2 takes 2 of them ; an accessory sold as it is takes none.
"""

from django.core.exceptions import ValidationError

from ..models import Order, Product
from .product_catalogue import kind_of, with_kind


def reference(order):
    return str(order.uuid)[:8].upper()


def item_of(order_id, item_index):
    """Line of an order, by its position in the order (the back-office lists the lines in that order)."""
    order = Order.objects.filter(uuid=order_id).prefetch_related("order_items").first()
    if order is None:
        raise ValidationError("Commande introuvable.")
    if order.status == "cancelled":
        raise ValidationError(f"La commande {reference(order)} est annulée.")
    items = sorted(order.order_items.all(), key=lambda i: i.pk)
    if item_index is None or not 0 <= item_index < len(items):
        raise ValidationError("Ligne de commande introuvable.")
    return items[item_index]


def check_room(item, model, exclude_pk=None):
    """An order line of quantity 2 takes 2 instruments (or pieces), not more."""
    linked = model.objects.filter(order_item=item).exclude(pk=exclude_pk).count()
    if linked >= item.quantity:
        raise ValidationError(
            f"« {item.product_name} » de la commande {reference(item.order)} a déjà tout ce qui a été commandé "
            f"({item.quantity})."
        )


def serialize(item):
    """Order line of an instrument or a piece, for its sheet in the back-office."""
    if item is None:
        return None
    order = item.order
    return {
        "id": str(order.uuid),
        "reference": reference(order),
        "status": order.status,
        "customer": " ".join(filter(None, [order.first_name, order.last_name])) or order.email,
        "item": item.product_name,
    }


def kinds(items):
    """What each order line needs from the workshop : "instrument" (a configured guitar), "part" (a piece sold
    alone) or None (sold as it is). Read from the product, in one query ; from the snapshot if it was deleted."""
    products = {
        p.uuid: kind_of(p) for p in with_kind(Product.objects.filter(uuid__in={item.product_id for item in items}))
    }
    result = {}
    for item in items:
        kind = products.get(item.product_id)
        if kind is None:  # product deleted : count the pieces made to measure in the snapshot
            pieces = _custom_pieces((item.config_snapshot or {}).get("options"))
            kind = "configurable" if pieces > 1 else "piece" if pieces == 1 else "simple"
        result[item.pk] = {"configurable": "instrument", "piece": "part"}.get(kind)
    return result


def _custom_pieces(snapshot):
    count = 0
    for component in snapshot if isinstance(snapshot, list) else [snapshot] if snapshot else []:
        if isinstance(component, dict):
            count += component.get("type") == "custom_piece"
            count += _custom_pieces(component.get("snapshot"))
    return count
