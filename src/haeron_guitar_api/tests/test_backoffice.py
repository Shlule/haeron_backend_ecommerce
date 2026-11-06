import pytest
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group

from haeron_backend.schema import schema

from ..models import InstrumentType, Option, PartType, Product, ProductSchema, ProductType


def run(query, user, **variables):
    return schema.execute_sync(query, variable_values=variables, context_value={"request": SimpleNamespace(user=user)})


@pytest.fixture
def staff(db):
    user = get_user_model().objects.create_user(username="staff", email="staff@example.com", password="x")
    user.groups.add(Group.objects.create(name="admin"))
    return user


def test_every_resource_is_described(staff):
    result = run("{ backoffice { resources } }", staff)
    assert result.errors is None
    names = [resource["name"] for resource in result.data["backoffice"]["resources"]]
    assert "PartModel" in names
    assert "User" not in names and "PartNFCIdentity" not in names


def test_create_update_delete(staff):
    created = run(
        "mutation ($data: BoOptionCreateInput!) { backoffice { createOption(data: $data) { uuid name } } }",
        staff,
        data={"name": "finish", "description": "Finition"},
    )
    assert created.errors is None
    pk = created.data["backoffice"]["createOption"]["uuid"]

    updated = run(
        "mutation ($data: BoOptionUpdateInput!) { backoffice { updateOption(data: $data) { name } } }",
        staff,
        data={"pk": pk, "name": "color"},
    )
    assert updated.errors is None
    assert Option.objects.get(pk=pk).name == "color"

    listed = run('{ backoffice { optionList(search: "col") { totalCount results { label } } } }', staff)
    assert listed.data["backoffice"]["optionList"]["totalCount"] == 1

    deleted = run("mutation ($pk: ID!) { backoffice { deleteOption(pk: $pk) } }", staff, pk=pk)
    assert deleted.data["backoffice"]["deleteOption"] is True
    assert not Option.objects.filter(pk=pk).exists()


def test_emptied_text_field_is_saved_as_empty(staff):
    product = Product.objects.create(
        name="Starlight",
        price=0,
        product_type=ProductType.objects.create(code="bundle"),
        product_schema=ProductSchema.objects.create(name="starlight", code="starlight"),
    )
    result = run(
        "mutation ($data: BoProductUpdateInput!) { backoffice { updateProduct(data: $data) { name } } }",
        staff,
        data={"pk": str(product.pk), "image": None, "model3d": "/models/starlight.glb"},
    )
    assert result.errors is None
    product.refresh_from_db()
    assert (product.image, product.model_3d) == ("", "/models/starlight.glb")


def test_validation_error_is_readable(staff):
    result = run(
        "mutation ($data: BoInstrumentTypeCreateInput!) { backoffice { createInstrumentType(data: $data) { name } } }",
        staff,
        data={"name": "Guitar", "code": "TOO_LONG"},
    )
    assert "code" in result.errors[0].message
    assert not InstrumentType.objects.exists()


def test_protected_row_is_not_deleted(staff, part_type, db):
    from ..models import PartModel

    PartModel.objects.create(name="neck", code="NCK", part_type=part_type)
    result = run("mutation ($pk: ID!) { backoffice { deletePartType(pk: $pk) } }", staff, pk=str(part_type.pk))
    assert "Suppression impossible" in result.errors[0].message
    assert PartType.objects.filter(pk=part_type.pk).exists()


def test_read_only_tables_have_no_mutation(staff):
    result = run("mutation { backoffice { createPart(data: {}) { uuid } } }", staff)
    assert "Cannot query field 'createPart'" in result.errors[0].message


def test_requires_a_staff_role(db):
    customer = get_user_model().objects.create_user(username="client", email="client@example.com", password="x")
    assert run("{ backoffice { optionList { totalCount } } }", AnonymousUser()).errors
    assert run("{ backoffice { optionList { totalCount } } }", customer).errors
