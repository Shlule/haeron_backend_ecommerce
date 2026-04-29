from django_filters import UUIDFilter, DateFromToRangeFilter, FilterSet


class CartItemFilterSet(FilterSet):
    id = UUIDFilter(field_name="uuid")

    cart_id = UUIDFilter(field_name="cart_id")
    product_id = UUIDFilter(field_name="product_id")

    create_at = DateFromToRangeFilter(field_name="created_at")
