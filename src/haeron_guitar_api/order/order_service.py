from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q, Sum

from ..models import Order, OrderItem, PartModel, PartModelOption, Payment
from ..payments.payment_service import PaymentService

STATUSES = dict(Order._meta.get_field("status").choices)


class OrderService:
    """Orders as seen by the back-office : list, technical sheet of each item, status change."""

    @staticmethod
    def list(offset=0, limit=50, status=None, search=None):
        orders = Order.objects.annotate(item_count=Sum("order_items__quantity")).order_by("-created_at")
        if status:
            orders = orders.filter(status=status)
        text = (search or "").strip()
        if text:
            orders = orders.filter(
                Q(uuid__istartswith=text)
                | Q(email__icontains=text)
                | Q(first_name__icontains=text)
                | Q(last_name__icontains=text)
                | Q(city__icontains=text)
            )
        limit = max(1, min(limit, 200))
        return {
            "totalCount": orders.count(),
            "results": [OrderService._summary(order) for order in orders[offset : offset + limit]],
        }

    @staticmethod
    def detail(order_uuid):
        order = (
            Order.objects.prefetch_related(
                Prefetch("order_items", queryset=OrderItem.objects.order_by("pk")),
                Prefetch("payments", queryset=Payment.objects.order_by("created_at")),
            )
            .filter(uuid=order_uuid)
            .first()
        )
        if order is None:
            return None
        items = list(order.order_items.all())
        payments = list(order.payments.all())
        unpaid = ["pending", "expired"]  # Stripe pages opened without paying
        catalog = OrderService._catalog(items)
        return {
            **OrderService._summary(order, item_count=sum(item.quantity for item in items)),
            "phone": order.phone,
            "address": order.address,
            "postalCode": order.postal_code,
            "country": order.country,
            "userId": str(order.user_id) if order.user_id else None,
            # Stripe pages left without paying are not shown
            "payments": [PaymentService.serialize(payment) for payment in payments if payment.status not in unpaid],
            # not paid yet : the link to give the customer, and how many Stripe pages were opened without paying
            "paymentLink": PaymentService.payment_link(order) if order.status == "pending" else None,
            "unpaidAttempts": sum(1 for p in payments if p.provider == "stripe" and p.status in [*unpaid, "failed"]),
            "items": [
                {
                    "productId": str(item.product_id),
                    "name": item.product_name,
                    "quantity": item.quantity,
                    "unitPrice": float(item.unit_price),
                    "total": float(item.unit_price * item.quantity),
                    "components": OrderService._components((item.config_snapshot or {}).get("options"), catalog),
                }
                for item in items
            ],
        }

    @staticmethod
    def set_status(order_uuid, status):
        if status not in STATUSES:
            raise ValidationError(f"Statut inconnu : {status}")
        order = Order.objects.filter(uuid=order_uuid).first()
        if order is None:
            raise ValidationError("Commande introuvable.")
        order.status = status
        order.save(update_fields=["status"])
        if status == "paid":
            # paid outside Stripe (transfer, cash) : the money still shows in the finances
            PaymentService.record_manual(order)
        return OrderService.detail(order_uuid)

    @staticmethod
    def _summary(order, item_count=None):
        return {
            "id": str(order.uuid),
            "reference": str(order.uuid)[:8].upper(),
            "status": order.status,
            "createdAt": order.created_at.isoformat(),
            "firstName": order.first_name,
            "lastName": order.last_name,
            "email": order.email,
            "city": order.city,
            "total": float(order.total_price or 0),
            "itemCount": item_count if item_count is not None else (getattr(order, "item_count", None) or 0),
        }

    @staticmethod
    def _catalog(items):
        """Current part models and option values used by the items, read in two queries.
        The snapshot stays the reference : the catalog only adds codes and prices."""
        part_model_ids, option_ids = set(), set()

        def collect(snapshot):
            for component in OrderService._as_list(snapshot):
                if component.get("part_model_id"):
                    part_model_ids.add(component["part_model_id"])
                option_ids.update(option["id"] for option in component.get("options", []) if option.get("id"))
                collect(component.get("snapshot"))

        for item in items:
            collect((item.config_snapshot or {}).get("options"))
        return {
            "part_models": {
                str(pm.uuid): pm for pm in PartModel.objects.select_related("part_type").filter(uuid__in=part_model_ids)
            },
            "options": {str(o.uuid): o for o in PartModelOption.objects.filter(uuid__in=option_ids)},
        }

    @staticmethod
    def _components(snapshot, catalog):
        components = []
        for component in OrderService._as_list(snapshot):
            part_model = catalog["part_models"].get(component.get("part_model_id") or "")
            components.append(
                {
                    "component": component.get("component", ""),
                    "type": component.get("type", ""),
                    "price": float(component["price"]) if component.get("price") not in (None, "") else None,
                    # piece made for this order
                    "partModel": (
                        {
                            "name": component.get("part_model") or (part_model.name if part_model else ""),
                            "code": part_model.code if part_model else "",
                            "partType": part_model.part_type.name if part_model else "",
                            "price": float(part_model.price) if part_model else None,
                        }
                        if component.get("type") == "custom_piece"
                        else None
                    ),
                    "options": [
                        {
                            "option": option.get("name", ""),
                            "value": option.get("value", ""),
                            "code": catalog["options"][option["id"]].code if option.get("id") in catalog["options"] else "",
                            "priceDelta": (
                                float(catalog["options"][option["id"]].price_delta)
                                if option.get("id") in catalog["options"]
                                else None
                            ),
                        }
                        for option in component.get("options", [])
                    ],
                    # product chosen, fixed or configured inside the bundle
                    "product": component.get("name") if component.get("type") != "custom_piece" else None,
                    "components": OrderService._components(component.get("snapshot"), catalog),
                }
            )
        return components

    @staticmethod
    def _as_list(snapshot):
        if not snapshot:
            return []
        return [c for c in (snapshot if isinstance(snapshot, list) else [snapshot]) if isinstance(c, dict)]
