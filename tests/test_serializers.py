from __future__ import unicode_literals

import unittest

from rdflib import URIRef, RDF

from r2dto_rdf import RdfSerializer, RdfIriField, RdfStringField, RdfObjectField, RdfSetField

from tests.utils import RdflibTestCaseMixin, get_triples


class SerializerTests(RdflibTestCaseMixin, unittest.TestCase):
    def test_basic_building_of_graph(self):
        class Model(object):
            def __init__(self):
                self.id = "http://api.nickswebsite.net/data#1"
                self.field = "xyz"

        class ModelSerializer(RdfSerializer):
            id = RdfIriField()
            field = RdfStringField(predicate="nws:field")

            class Meta:
                model = Model
                rdf_prefixes = {
                    "nws": "http://api.nickswebsite.net/ns/",
                    "nws-data": "http://api.nickswebsite.net/data#"
                }
                rdf_subject = "id"
                rdf_type = "nws:Type"

        m = Model()
        s = ModelSerializer(object=m)

        g = s.build_graph()

        self.assert_triple(g,
                           "http://api.nickswebsite.net/data#1",
                           "http://api.nickswebsite.net/ns/field",
                           "xyz")

        self.assert_triple(g,
                           "http://api.nickswebsite.net/data#1",
                           RDF.type,
                           "http://api.nickswebsite.net/ns/Type")

    def test_data_types(self):
        class Model(object):
            def __init__(self):
                self.field = "ABC"
                self.id = "http://api.nickswebsite.net/data#1"

        class ModelSerializer(RdfSerializer):
            field = RdfStringField(predicate="nws:field", datatype="nws:Stringish")

            class Meta:
                rdf_subject = "id"
                rdf_prefixes = {
                    "nws": "http://api.nickswebsite.net/ns/",
                    "nws-data": "http://api.nickswebsite.net/data#"
                }

        m = Model()
        s = ModelSerializer(object=m)
        g = s.build_graph()
        self.assert_triple(g,
                           "http://api.nickswebsite.net/data#1",
                           "http://api.nickswebsite.net/ns/field",
                           "ABC",
                           datatype="http://api.nickswebsite.net/ns/Stringish")

    def test_language(self):
        class Model(object):
            def __init__(self):
                self.field = "aef"
                self.id = "http://api.nickswebsite.net/data#1"

        class ModelSerializer(RdfSerializer):
            field = RdfStringField(predicate="nws:field",
                                   language="en")

            class Meta:
                rdf_subject = "id"
                rdf_prefixes = {
                    "nws": "http://api.nickswebsite.net/ns/",
                    "nws-data": "http://api.nickswebsite.net/data#"
                }

        m = Model()
        s = ModelSerializer(object=m)
        g = s.build_graph()
        self.assert_triple(g,
                           "http://api.nickswebsite.net/data#1",
                           "http://api.nickswebsite.net/ns/field",
                           "aef",
                           language="en")

    def test_sub_objects_collapsed(self):
        class SubModel(object):
            def __init__(self):
                self.field_one = "field one"

        class Model(object):
            def __init__(self):
                self.id = "http://api.nickswebsite.net/data#1"
                self.field = "Field"
                self.sub_field = SubModel()

        class SubModelSerializer(RdfSerializer):
            field_one = RdfStringField(predicate="nws:sub-field")

            class Meta:
                rdf_prefixes = {"nws": "http://www.nickswebsite.net/ns/"}

        class ModelSerializer(RdfSerializer):
            sub_field = RdfObjectField(SubModelSerializer, collapse=True)
            field = RdfStringField(predicate="nws:field")

            class Meta:
                rdf_prefixes = {"nws": "http://www.nickswebsite.net/ns/"}
                rdf_subject = "id"

        m = Model()
        s = ModelSerializer(object=m)
        g = s.build_graph()
        self.assert_triple(g, m.id, "http://www.nickswebsite.net/ns/sub-field", "field one")

    def test_sub_objects_with_blank_nodes(self):
        class SubModel(object):
            def __init__(self):
                self.one = "Field One"

        class Model(object):
            def __init__(self):
                self.sub_field = SubModel()
                self.id = "http://api.nickswebsite.net/data#1"

        class SubModelSerializer(RdfSerializer):
            one = RdfStringField(predicate="nws:one")

            class Meta:
                rdf_prefixes = {"nws": "http://api.nickswebsite.net/ns/"}

        class ModelSerializer(RdfSerializer):
            sub_field = RdfObjectField(SubModelSerializer, "nws:sub-field", collapse=False)

            class Meta:
                rdf_prefixes = {"nws": "http://api.nickswebsite.net/ns/"}
                rdf_subject = "id"

        m = Model()
        s = ModelSerializer(object=m)
        s.validate()
        g = s.build_graph()

        result = get_triples(g, "http://api.nickswebsite.net/data#1", "http://api.nickswebsite.net/ns/sub-field", None)
        result = list(result)
        result_submodel_triples = get_triples(g, result[0][-1], None, None)
        result_submodel_triples = list(result_submodel_triples)

        self.assert_uri_equal("http://api.nickswebsite.net/ns/one", result_submodel_triples[0][1])
        self.assert_literal_equal("Field One", result_submodel_triples[0][2])

    def test_set_objects_collapsed(self):
        class Model(object):
            def __init__(self):
                self.id = "http://api.nickswebsite.net/data#2"
                self.fields = ["String One", "String Two"]

        class ModelSerializer(RdfSerializer):
            fields = RdfSetField(RdfStringField(), predicate="nws:field", collapse=True)

            class Meta:
                rdf_prefixes = {
                    "nws": "http://api.nickswebsite.net/ns/",
                    "nws-data": "http://api.nickswebsite.net/data#"
                }
                rdf_subject = "id"

        m = Model()
        s = ModelSerializer(object=m)
        s.validate()
        g = s.build_graph()

        self.assert_triple(g, m.id, "http://api.nickswebsite.net/ns/field", "String One")
        self.assert_triple(g, m.id, "http://api.nickswebsite.net/ns/field", "String Two")

    def test_objects_as_ids(self):
        class Model(object):
            def __init__(self):
                self.id = "http://api.nickswebsite.net/data#3"
                self.link = "http://api.nickswebsite.net/data#3"

        class ModelSerializer(RdfSerializer):
            class Meta:
                rdf_subject = "id"

            link = RdfIriField(predicate="http://api.nickswebsite.net/ns/link")

        model = Model()
        s = ModelSerializer(object=model)
        s.validate()
        g = s.build_graph()
        triples = list(get_triples(g, model.id, "http://api.nickswebsite.net/ns/link", None))
        self.assertEqual(URIRef(model.link), triples[0][-1])

    def test_objects_in_lists(self):
        class SubModel(object):
            def __init__(self, val):
                self.val = val

        class Model(object):
            def __init__(self):
                self.values = [SubModel("One"), SubModel("Two")]
                self.id = "http://api.nickswebsite.net/data#8"

        class SubModelSerializer(RdfSerializer):
            val = RdfStringField(predicate="http://api.nickswebsite.net/ns/value")

        class ModelSerializer(RdfSerializer):
            values = RdfSetField(
                RdfObjectField(SubModelSerializer),
                predicate="http://api.nickswebsite.net/ns/sub-object"
            )

            class Meta:
                rdf_subject = "id"

        # @prefix nws: <http://api.nickswebsite.net/>
        #
        # nws:data#8 nws:ns/sub-object [ nws:ns/value "One" ],
        #                              [ nws:ns/value "Two" ] .
        #
        m = Model()
        s = ModelSerializer(object=m)
        s.validate()
        g = s.build_graph()

        model_triples = get_triples(g, m.id, "http://api.nickswebsite.net/ns/sub-object", None)
        self.assertEqual(2, len(model_triples))

        submodel_triples_a = get_triples(g, model_triples[0][2], "http://api.nickswebsite.net/ns/value", None)
        submodel_triples_b = get_triples(g, model_triples[1][2], "http://api.nickswebsite.net/ns/value", None)
        self.assertEqual({"One", "Two"}, {submodel_triples_a[0][2].value, submodel_triples_b[0][2].value})

    def test_non_required_none_fields(self):
        class Model(object):
            def __init__(self):
                self.prop = "value"
                self.none = None
                self.id = "http://api.nickswebsite.net/data#9"

        class ModelSerializer(RdfSerializer):
            prop = RdfStringField(predicate="http://api.nickswebsite.net/ns/prop")
            none = RdfIriField(predicate="http://api.nickswebsite.net/ns/none", required=False)

            class Meta:
                rdf_subject = "id"

        m = Model()
        s = ModelSerializer(object=m)
        s.validate()
        g = s.build_graph()

        prop_triples = get_triples(g, m.id, "http://api.nickswebsite.net/ns/prop", None)
        self.assertEqual(1, len(prop_triples))
        self.assertEqual(m.prop, prop_triples[0][-1].toPython())
        none_triples = get_triples(g, m.id, "http://api.nickswebsite.net/ns/none", None)
        self.assertEqual(0, len(none_triples))
