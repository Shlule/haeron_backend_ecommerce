from pprint import pprint
from django.db import IntegrityError
from django.test import TestCase
from strawberry_django.test.client import TestClient

from ..models import PartType, InstrumentType


class InstrumentTypeGQLTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.partType1 = PartType.objects.create(name="neck", code="NCK")
        cls.partType2 = PartType.objects.create(name="body", code="BDY")

        cls.instrumentType1 = InstrumentType.objects.create(name="test guitar", code="TG")
        cls.instrumentType2 = InstrumentType.objects.create(name="testPiano", code="TP")

        cls.instrumentType1.part_types.add(cls.partType1)
        cls.instrumentType2.part_types.add(cls.partType2)

    def setUp(self):
        self.client = TestClient(path="/graphql/")

    def test_get_instrument_type_by_id(self):
        query_p = """
        query($id : String!){
            instrumentTypes(filters:{id: $id}){
                name
                code
            }
        }
"""
        response = self.client.query(query_p, variables={"id": str(self.instrumentType1.uuid)})
        self.assertIsNone(response.errors)
        self.assertEqual(response.data["instrumentTypes"][0]["name"], "test guitar")

    def test_get_instrument_type_by_name(self):
        query_p = """
        query($name : String!){
            instrumentTypes(filters:{name: $name}){
                name
                code
            }
        }
"""
        response = self.client.query(query_p, variables={"name": str(self.instrumentType1.name)})
        self.assertIsNone(response.errors)
        self.assertEqual(response.data["instrumentTypes"][0]["name"], "test guitar")

    def test_get_instrument_type_by_code(self):
        query_p = """
        query($code : String!){
            instrumentTypes(filters:{code: $code}){
                name
                code
            }
        }
"""
        response = self.client.query(query_p, variables={"code": str(self.instrumentType1.code)})
        self.assertIsNone(response.errors)
        self.assertEqual(response.data["instrumentTypes"][0]["name"], "test guitar")

    def test_instrument_type_unique_name(self):
        with self.assertRaises(IntegrityError):
            InstrumentType.objects.create(name="test guitar", code="caca")

    def test_instrument_type_unique_code(self):
        with self.assertRaises(IntegrityError):
            InstrumentType.objects.create(name="caca", code="TG")

    def test_adding_part_types(self):
        partType3 = PartType.objects.create(name="ahah", code="ohoh")
        partType4 = PartType.objects.create(name="caca", code="prout")

        query_p = """
        mutation($instrument_type_id: UUID!, $part_types_ids: [UUID!]! ){
            addInstrumentTypePartTypeConnec(instrumentTypeId: $instrument_type_id, partTypesIds: $part_types_ids)
        }
"""
        response = self.client.query(
            query_p,
            variables={
                "instrument_type_id": str(self.instrumentType1.uuid),
                "part_types_ids": [partType3.uuid, partType4.uuid],
            },
        )
        self.assertEqual(response.data["addInstrumentTypePartTypeConnec"], True)

        query_p_deux = """
                query($id: String!){
                    instrumentTypes(filters:{id: $id}){
                        partTypes{
                            name
                            code
                        }
                    }
                }
        """
        response_deux = self.client.query(query_p_deux, variables={"id": str(self.instrumentType1.uuid)})
        self.assertIsNone(response_deux.errors)
        self.assertEqual(len(response_deux.data["instrumentTypes"][0]["partTypes"]), 3)

    def test_remove_instrument_types(self):
        partType3 = PartType.objects.create(name="ahah", code="ohoh")
        partType4 = PartType.objects.create(name="caca", code="prout")

        self.instrumentType1.part_types.add(partType3, partType4)
        query_p = """
        mutation($instrument_type_id: UUID!, $part_types_ids: [UUID!]! ){
            rmInstrumentTypePartTypeConnec(instrumentTypeId: $instrument_type_id, partTypesIds: $part_types_ids)
        }
"""
        response = self.client.query(
            query_p,
            variables={
                "instrument_type_id": str(self.instrumentType1.uuid),
                "part_types_ids": [partType3.uuid, partType4.uuid],
            },
        )
        self.assertEqual(response.data["rmInstrumentTypePartTypeConnec"], True)

        query_p_deux = """
                query($id: String!){
                    instrumentTypes(filters:{id: $id}){
                        partTypes{
                            name
                            code
                        }
                    }
                }
        """
        response_deux = self.client.query(query_p_deux, variables={"id": str(self.instrumentType1.uuid)})
        self.assertIsNone(response_deux.errors)
        self.assertEqual(len(response_deux.data["instrumentTypes"][0]["partTypes"]), 1)
