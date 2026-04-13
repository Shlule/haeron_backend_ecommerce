from django.db.models import Q
from django_filters import FilterSet, CharFilter, UUIDFilter
from ..models import PartType


class PartTypeFilterSet(FilterSet):
    id = UUIDFilter(field_name="uuid")
    name = CharFilter(field_name="name")
    code = CharFilter(field_name="code")

    class Meta:
        model = PartType
        fields = ["id", "name", "code"]
