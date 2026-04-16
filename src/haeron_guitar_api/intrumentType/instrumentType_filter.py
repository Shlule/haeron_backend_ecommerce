from django_filters import FilterSet, CharFilter, UUIDFilter


class InstrumentTypeFilterSet(FilterSet):
    id = UUIDFilter(field_name="uuid")
    name = CharFilter(field_name="name")
    code = CharFilter(field_name="code")
