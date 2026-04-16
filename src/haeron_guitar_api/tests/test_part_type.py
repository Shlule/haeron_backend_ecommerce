from pprint import pprint
from django.db import IntegrityError
from django.test import TestCase
from strawberry_django.test.client import TestClient

from ..models import PartType, InstrumentType


class PartTypeGQLTest(TestCase):
    @classmethod
    def setUpTestData(cls):

        cls.instrumentType1 = InstrumentType.objects.create(name="test guitar", code="TG")
        cls.instrumentType2 = InstrumentType.objects.create(name="test piano", code="TP")

        cls.partType1 = PartType.objects.create(name="body", code="BDY")
        cls.partType1.instrument_types.add(cls.instrumentType1)

        cls.partType2 = PartType.objects.create(name="neck", code="NCK")
        cls.partType2.instrument_types.add(cls.instrumentType2)

    def setUp(self):
        self.client = TestClient(path="/graphql/")

    def test_get_part_type_by_id(self):

        query_p = """
        query($id: String!){
            partTypes(filters:{id: $id}){
                name
                code
            }
        }
    """

        response = self.client.query(query_p, variables={"id": str(self.partType1.uuid)})
        self.assertIsNone(response.errors)
        self.assertEqual(response.data["partTypes"][0]["name"], "body")

    def test_get_part_type_by_name(self):
        query_p = """
        query($name: String!){
            partTypes(filters:{name: $name}){
                name
                code
            }
        }
"""
        response = self.client.query(query_p, variables={"name": str(self.partType1.name)})
        self.assertIsNone(response.errors)
        self.assertEqual(response.data["partTypes"][0]["name"], "body")

    def test_get_part_type_by_code(self):
        query_p = """
        query($code: String!){
            partTypes(filters:{code: $code}){
                name
                code
            }
        }
"""
        response = self.client.query(query_p, variables={"code": str(self.partType1.code)})
        self.assertIsNone(response.errors)
        self.assertEqual(response.data["partTypes"][0]["code"], "BDY")

    def test_part_type_unique_name(self):
        with self.assertRaises(IntegrityError):
            PartType.objects.create(name="body", code="lolo")

    def test_part_type_unique_code(self):
        with self.assertRaises(IntegrityError):
            PartType.objects.create(name="ahah", code="BDY")

    def test_adding_instrument_types(self):
        instrumentType3 = InstrumentType.objects.create(name="ahah", code="ohoh")
        instrumentType4 = InstrumentType.objects.create(name="caca", code="prout")

        query_p = """
        mutation($part_type_id: UUID!, $instrument_types_ids: [UUID!]! ){
            addPartTypeInstrumentTypeConnec(partTypeId: $part_type_id, instrumentTypeIds: $instrument_types_ids)
        }
"""
        response = self.client.query(
            query_p,
            variables={
                "part_type_id": str(self.partType1.uuid),
                "instrument_types_ids": [instrumentType3.uuid, instrumentType4.uuid],
            },
        )
        self.assertEqual(response.data["addPartTypeInstrumentTypeConnec"], True)

        query_p_deux = """
                query($id: String!){
                    partTypes(filters:{id: $id}){
                        instrumentTypes{
                            name
                            code
                        }
                    }
                }
        """
        response_deux = self.client.query(query_p_deux, variables={"id": str(self.partType1.uuid)})
        self.assertIsNone(response_deux.errors)
        self.assertEqual(len(response_deux.data["partTypes"][0]["instrumentTypes"]), 3)

    def test_remove_instrument_types(self):
        instrumentType3 = InstrumentType.objects.create(name="ahah", code="ohoh")
        instrumentType4 = InstrumentType.objects.create(name="prout", code="caca")

        self.partType1.instrument_types.add(instrumentType3, instrumentType4)
        query_p = """
        mutation($part_type_id: UUID!, $instrument_types_ids: [UUID!]! ){
            rmPartTypeInstrumentTypeConnec(partTypeId: $part_type_id, instrumentTypeIds: $instrument_types_ids)
        }
"""
        response = self.client.query(
            query_p,
            variables={
                "part_type_id": str(self.partType1.uuid),
                "instrument_types_ids": [instrumentType3.uuid, instrumentType4.uuid],
            },
        )
        self.assertEqual(response.data["rmPartTypeInstrumentTypeConnec"], True)

        query_p_deux = """
                query($id: String!){
                    partTypes(filters:{id: $id}){
                        instrumentTypes{
                            name
                            code
                        }
                    }
                }
        """
        response_deux = self.client.query(query_p_deux, variables={"id": str(self.partType1.uuid)})
        self.assertIsNone(response_deux.errors)
        self.assertEqual(len(response_deux.data["partTypes"][0]["instrumentTypes"]), 1)
