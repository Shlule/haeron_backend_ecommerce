"""Number of SQL queries of the main calls : it must not grow with the number of components, rules or rows.
A failure here usually means a loop now reads the database (add a select_related / prefetch_related)."""

from django.db import connection
from django.test.utils import CaptureQueriesContext

from haeron_guitar_api.models import PartModelOption

from .product_configurator.test_configurator import starlight  # noqa: F401  (fixture)
from .test_backoffice import run as run_staff, staff  # noqa: F401  (helper and fixture)
from .test_backoffice_orders import order  # noqa: F401  (fixture)
from .test_storefront import run as run_shop


def count(call):
    with CaptureQueriesContext(connection) as queries:
        result = call()
    assert result.errors is None, result.errors
    return len(queries)


def test_configurator_queries_do_not_depend_on_the_schema_size(starlight):  # noqa: F811
    s = starlight
    template = count(lambda: run_shop("query ($id: UUID!) { configuratorTemplate(productId: $id) }", id=str(s["product"].uuid)))
    validate = count(
        lambda: run_shop(
            "query ($id: UUID!, $c: JSON!) { validateConfiguration(productId: $id, configuration: $c) }",
            id=str(s["product"].uuid),
            c=s["configuration"](s["alu"], s["blue"]),
        )
    )
    assert template <= 12
    assert validate <= 12


def test_backoffice_list_reads_linked_rows_with_the_page(staff, starlight):  # noqa: F811
    selection = "uuid code label partModel { uuid label } option { uuid label }"
    query = f"{{ backoffice {{ partModelOptionList(limit: 50) {{ totalCount results {{ {selection} }} }} }} }}"
    few = count(lambda: run_staff(query, staff))
    # more rows : same number of queries
    part_model_option = PartModelOption.objects.first()
    for index in range(10):
        PartModelOption.objects.create(
            part_model=part_model_option.part_model, option=part_model_option.option, name=f"v{index}", code=f"v{index}"
        )
    assert count(lambda: run_staff(query, staff)) == few <= 4


def test_order_sheet_queries(staff, order):  # noqa: F811
    sheet = "query ($id: UUID!) { backoffice { orderSheet(orderId: $id) } }"
    assert count(lambda: run_staff(sheet, staff, id=str(order.uuid))) <= 6
    assert count(lambda: run_shop("query ($id: UUID!) { shopOrder(orderId: $id) }", id=str(order.uuid))) <= 2
