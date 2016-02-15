from __future__ import unicode_literals

import unittest

import r2dto

from r2dto_rdf import create_rdf_serializer_from_r2dto_serializer

from tests.utils import RdflibTestCaseMixin, get_triples


class R2DtoMappingTests(RdflibTestCaseMixin, unittest.TestCase):
    def test_generate_from_r2dto(self):
        class Model(object):
            def __init__(self):
                self.id = "http://api.nickswebsite.net/data#5"
                self.field = "Some Field"

        class ModelSerializer(r2dto.Serializer):
            field = r2dto.fields.StringField()
            id = r2dto.fields.StringField(required=True, allow_null=False)

            class Meta:
                model = Model
                rdf_subject = "id"
                rdf_prefixes = {
                    "nws": "http://api.nickswebsit.net/ns/",
                }

            class Rdf:
                field = "nws:field"

        RdfModelSerializer = create_rdf_serializer_from_r2dto_serializer(ModelSerializer)

        m = Model()
        s = RdfModelSerializer(object=m)
        g = s.build_graph()
        self.assert_triple(g, "http://api.nickswebsite.net/data#5", "http://api.nickswebsit.net/ns/field", "Some Field")

    def test_generate_from_from_r2dto_lists(self):
        class Model(object):
            def __init__(self):
                self.id = "http://api.nickswebsite.net/data#1"
                self.items = ["Item One", "Item Two"]

        class ModelSerializer(r2dto.Serializer):
            class Meta:
                rdf_subject = "id"

            class Rdf:
                items = "http://api.nickswebsite.net/ns/item"

            items = r2dto.fields.ListField(r2dto.fields.StringField())

        RdfModelSerializer = create_rdf_serializer_from_r2dto_serializer(ModelSerializer)

        m = Model()
        s = RdfModelSerializer(object=m)
        g = s.build_graph()
        s.validate()
        self.assert_triple(g, "http://api.nickswebsite.net/data#1", "http://api.nickswebsite.net/ns/item", "Item One")
        self.assert_triple(g, "http://api.nickswebsite.net/data#1", "http://api.nickswebsite.net/ns/item", "Item Two")

    def test_generate_from_r2dto_objects(self):
        class SubModel(object):
            def __init__(self):
                self.sub_field = "Some Field"

        class Model(object):
            def __init__(self):
                self.sub_model = SubModel()
                self.id = "http://api.nickswebsite.net/data#1"

        class SubModelSerializer(r2dto.Serializer):
            sub_field = r2dto.fields.StringField(name="subField")

            class Meta:
                rdf_prefixes = {
                    "nws": "http://api.nickswebsite.net/ns/",
                }

            class Rdf:
                sub_field = "nws:sub-field"

        class ModelSerializer(r2dto.Serializer):
            sub_model = r2dto.fields.ObjectField(SubModelSerializer, name="subModel", required=True)

            class Meta:
                rdf_subject = "id"
                rdf_prefixes = {
                    "nws": "http://api.nickswebsite.net/ns/",
                }

            class Rdf:
                sub_model = "@collapse"

        RdfModelSerializer = create_rdf_serializer_from_r2dto_serializer(ModelSerializer)

        m = Model()
        s = RdfModelSerializer(object=m)
        s.validate()
        g = s.build_graph()
        self.assert_triple(g,
                           "http://api.nickswebsite.net/data#1",
                           "http://api.nickswebsite.net/ns/sub-field",
                           "Some Field")

    def test_object_list_fields(self):
        class SubModel(object):
            def __init__(self, field):
                self.field = field

        class Model(object):
            def __init__(self, *args):
                self.fields = [SubModel(arg) for arg in args]
                self.id = "http://api.nickswebsite.net/data#1"

        class SubModelSerializer(r2dto.Serializer):
            field = r2dto.fields.StringField()

            class Meta:
                rdf_prefixes = {
                    "nws": "http://api.nickswebsite.net/ns/",
                }

            class Rdf:
                field = "nws:field"

        class ModelSerializer(r2dto.Serializer):
            fields = r2dto.fields.ListField(r2dto.fields.ObjectField(SubModelSerializer))

            class Meta:
                rdf_prefixes = {
                    "nws": "http://api.nickswebsite.net/ns/",
                }
                rdf_subject = "id"

            class Rdf:
                fields = "nws:fields"

        RdfModelSerializer = create_rdf_serializer_from_r2dto_serializer(ModelSerializer)

        m = Model("One", "Two")
        s = RdfModelSerializer(object=m)
        g = s.build_graph()
        ###
        # @prefix nws: <http://api.nickswebsite.net/
        #
        # nws:data#1 nws:ns/fields [ nws:field "One" ],
        #                          [ nws:field "Two" ] .
        model_triples = get_triples(g, m.id, "http://api.nickswebsite.net/ns/fields", None)
        self.assertEqual(2, len(model_triples))

        submodel_triples_a = get_triples(g, model_triples[0][2], "http://api.nickswebsite.net/ns/field", None)
        submodel_triples_b = get_triples(g, model_triples[1][2], "http://api.nickswebsite.net/ns/field", None)
        self.assertEqual({"One", "Two"}, {submodel_triples_a[0][2].value, submodel_triples_b[0][2].value})
