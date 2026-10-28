from django_filters import FilterSet, CharFilter, UUIDFilter


class OptionFilterSet(FilterSet):
    id = UUIDFilter(field_name="uuid")
    category = CharFilter(field_name="category")
