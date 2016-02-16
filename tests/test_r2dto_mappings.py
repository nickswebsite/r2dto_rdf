from __future__ import unicode_literals

import datetime
import unittest
import uuid

import r2dto

from r2dto_rdf import RdfR2DtoSerializer, create_rdf_serializer_from_r2dto_serializer, RdfUuidField

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

    def test_big_mess_simple_types(self):
        class Model(object):
            def __init__(self):
                self.uuid = uuid.uuid4()
                self.datetime = datetime.datetime(2014, 2, 1, 2, 3)
                self.date = datetime.date(2015, 3, 1)
                self.time = datetime.time(2, 32)
                self.uuid_iri = uuid.uuid4()
                self.string = "Some String"
                self.boolean = True
                self.integer = 32
                self.float = 44.123
                self.id = "http://api.nickswebsite.net/data#921"

        class ModelSerializer(r2dto.Serializer):
            uuid = r2dto.fields.UuidField()
            datetime = r2dto.fields.DateTimeField()
            date = r2dto.fields.DateField()
            time = r2dto.fields.TimeField()
            uuid_iri = r2dto.fields.UuidField()
            integer = r2dto.fields.IntegerField()
            float = r2dto.fields.FloatField()
            string = r2dto.fields.StringField()
            boolean = r2dto.fields.BooleanField()

            class Meta:
                rdf_subject = "id"
                rdf_prefixes = {
                    "nws": "http://api.nickswebsite.net/"
                }

        class Rdf:
            uuid_iri = RdfUuidField(predicate="nws:ns/uuid", iri=True)
            uuid = "nws:ns/uuid"
            datetime = "nws:ns/date-time"
            date = "nws:ns/date"
            time = "nws:ns/time"
            integer = "nws:ns/integer"
            float = "nws:ns/float"
            string = "nws:ns/string"
            boolean = "nws:ns/boolean"

        def create_serializer_with_rdf_class():
            ModelSerializer.Rdf = Rdf
            res = create_rdf_serializer_from_r2dto_serializer(ModelSerializer)
            del ModelSerializer.Rdf
            return res

        def create_serializer_with_rdf_parameter():
            return create_rdf_serializer_from_r2dto_serializer(ModelSerializer, Rdf)

        for create_serializer in (create_serializer_with_rdf_parameter, create_serializer_with_rdf_class):
            RdfModelSerializer = create_serializer()

            m = Model()
            s = RdfModelSerializer(object=m)
            s.validate()
            g = s.build_graph()

            self.assert_triple(g,
                               m.id,
                               s.namespace_manager.resolve_term("nws:ns/string"),
                               m.string)
            self.assert_triple(g,
                               m.id,
                               s.namespace_manager.resolve_term("nws:ns/boolean"),
                               m.boolean)
            self.assert_triple(g,
                               m.id,
                               s.namespace_manager.resolve_term("nws:ns/integer"),
                               m.integer)
            self.assert_triple(g,
                               m.id,
                               s.namespace_manager.resolve_term("nws:ns/float"),
                               m.float)
            self.assert_triple(g,
                               m.id,
                               s.namespace_manager.resolve_term("nws:ns/date-time"),
                               m.datetime)
            self.assert_triple(g,
                               m.id,
                               s.namespace_manager.resolve_term("nws:ns/date"),
                               m.date)
            self.assert_triple(g,
                               m.id,
                               s.namespace_manager.resolve_term("nws:ns/time"),
                               m.time)
            self.assert_triple(g,
                               m.id,
                               s.namespace_manager.resolve_term("nws:ns/uuid"),
                               str(m.uuid))
            self.assert_triple(g,
                               m.id,
                               s.namespace_manager.resolve_term("nws:ns/uuid"),
                               "urn:uuid:" + str(m.uuid_iri))

    def test_rdf_r2dto_serializer(self):
        class Model(object):
            def __init__(self):
                self.field = "Some Field"
                self.id = "http://api.nickswebsite.net/data#1"

        class ModelSerializer(r2dto.Serializer):
            field = r2dto.fields.StringField()

            class Meta:
                model = Model

        class ModelRdfSerializer(RdfR2DtoSerializer):
            class Meta:
                serializer_class = ModelSerializer
                rdf_subject = "id"
                rdf_prefixes = {
                    "nws": "http://api.nickswebsite.net/"
                }

            class Rdf:
                field = "nws:field"

        m = Model()
        s = ModelRdfSerializer(object=m)
        g = s.build_graph()

        self.assert_triple(g, m.id, s.namespace_manager.resolve_term("nws:field"), "Some Field")
