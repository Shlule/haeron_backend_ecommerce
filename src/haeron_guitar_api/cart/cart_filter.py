from django_filters import FilterSet, UUIDFilter, DateFilter, DateFromToRangeFilter, BooleanFilter


class CartFilterSet(FilterSet):
    id = UUIDFilter(field_name="uuid")
    create_at = DateFilter(field_name="create_at")
    create_after = DateFilter(field_name="create_at", lookup_expr="gte")
    create_before = DateFilter(field_name="create_at", lookup_expr="lte")
    create_between = DateFromToRangeFilter(field_name="create_at")
    expires_at = DateFilter(field_name="expires_at")
    expires_after = DateFilter(field_name="expires_at", lookup_expr="gte")
    expires_before = DateFilter(field_name="expires_at", lookup_expr="lte")
    expires_between = DateFromToRangeFilter(field_name="expires_at")
    user_id = UUIDFilter(field_name="user__uuid")
    is_active = BooleanFilter(field_name="is_active")
