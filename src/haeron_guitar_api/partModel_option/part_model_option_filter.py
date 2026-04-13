from django_filters import CharFilter, UUIDFilter, FilterSet


class PartModelOptionFIlterSet(FilterSet):
    id = UUIDFilter(field_name="uuid")
    name = CharFilter(field_name="name", lookup_expr="icontains")

    option = CharFilter(method="option_id_filter")
    option_name = CharFilter(method="option_name_filter")
    option_category = CharFilter(method="option_category_filter")

    part_model = CharFilter(method="partModel_id_filter")
    part_model_name = CharFilter(method="partModel_name_filter")
    part_model_code = CharFilter(method="partModel_code_filter")

    def option_name_filter(self, queryset, name, value):
        return queryset.filter(option__name__icontains=value)

    def option_id_filter(self, queryset, name, value):
        return queryset.filter(option__uuid=value)

    def option_category_filter(self, queryset, name, value):
        return queryset.filter(option__category=value)

    def partModel_id_filter(self, queryset, name, value):
        return queryset.filter(part_model__uuid=value)

    def partModel_name_filter(self, queryset, name, value):
        return queryset.filter(part_model__name__icontains=value)

    def partModel_code_filter(self, queryset, name, value):
        return queryset.filter(part_model__code=value)
