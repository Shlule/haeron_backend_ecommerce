from django.db.models import Q
from django_filters import FilterSet, CharFilter, UUIDFilter
from ..models import PartType

class PartTypeFilterSet(FilterSet):
    id = UUIDFilter(field_name="id")
    name = CharFilter(method="filter_name")
    code = CharFilter(method="filter_code")

    class Meta:
        model = PartType
        fields = ["id", "name", "code"]

    def filter_name(self, queryset, name, value):
        # recherche insensible à la casse et partial match
        return queryset.filter(Q(name__icontains=value))

    def filter_code(self, queryset, name, value):
        return queryset.filter(Q(code__icontains=value))