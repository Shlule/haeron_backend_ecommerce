from django_filters import FilterSet, UUIDFilter, DateFilter
from ..models import SerialCounter


class SerialCounterFilterSet(FilterSet):
    factory_id = UUIDFilter(field_name="factory__uuid")  # filtre par factory
    year = DateFilter(field_name="year")  # filtre par date
    date_before = DateFilter(field_name="year", lookup_expr="lte")  # avant ou égal
    date_after = DateFilter(field_name="year", lookup_expr="gte")  # après ou égal

    class Meta:
        model = SerialCounter
        fields = ["factory_id", "year", "date_before", "date_after"]
