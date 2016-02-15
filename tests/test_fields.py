from __future__ import unicode_literals

import datetime
import unittest
import uuid

from rdflib import URIRef

from r2dto_rdf import ValidationError, RdfIriField, RdfStringField, RdfObjectField, RdfSetField, RdfSerializer, \
    RdfBooleanField, RdfIntegerField, RdfFloatField, RdfDateField, RdfUuidField
from r2dto_rdf.fields import RdfDateTimeField, RdfTimeField
from r2dto_rdf.serializer import RdflibNamespaceManager

from tests.utils import RdflibTestCaseMixin, get_triples


class FieldTests(RdflibTestCaseMixin, unittest.TestCase):
    def test_iri_field(self):
        f = RdfIriField("http://api.nickswebsite.net/data#1")

        res = f.render("http://api.nickswebsite.net/data#2")
        self.assertEqual(res, "http://api.nickswebsite.net/data#2")

        f.validate("http://api.nickswebstie.net/data#2")

        self.assertRaises(ValidationError, f.validate, "some-non-iri")

    def test_string_field(self):
        f = RdfStringField("nws:test-field")

        errors = f.get_configuration_errors()
        self.assertIsNone(errors)

        expected = "This is some \u2012 unicode."
        self.assertEqual(expected, f.render(expected))

        self.assertRaises(ValidationError, f.validate, 3)

    def test_boolean_field(self):
        f = RdfBooleanField("nws:test-field", True)

        errors = f.get_configuration_errors()
        self.assertIsNone(errors)

        expected = True
        self.assertEqual(expected, f.render(expected))

        f.validate(True)
        f.validate(False)

        self.assertRaises(ValidationError, f.validate, "123")

    def test_integer_field(self):
        f = RdfIntegerField("nws:test-field")

        errors = f.get_configuration_errors()
        self.assertIsNone(errors)

        expected = 34
        self.assertEqual(expected, f.render(expected))

        self.assertRaises(ValidationError, f.validate, "123")
        self.assertRaises(ValidationError, f.validate, 12.0)
        self.assertRaises(ValidationError, f.validate, True)

    def test_float_field(self):
        f = RdfFloatField("nws:test-field")

        errors = f.get_configuration_errors()
        self.assertIsNone(errors)

        expected = 2.34
        self.assertEqual(expected, f.render(expected))

        self.assertRaises(ValidationError, f.validate, "ABC")
        self.assertRaises(ValidationError, f.validate, True)

    def test_list_field(self):
        subject = URIRef("http://api.nickswebsite.net/data#1")
        p = "http://api.nickswebsite.net/list-item"

        f = RdfSetField(RdfStringField(), predicate=p)

        # TODO this shouldn't need to happen.
        class S(object):
            namespace_manager = RdflibNamespaceManager()
        f.parent = S()

        f.validate(["A", "B", "C"])
        self.assertRaises(ValidationError, f.validate, ["A", 2, "C"])

        g = f.build_graph(["A", "B", "C"], subject)
        self.assert_triple(g, subject, p, "A")
        self.assert_triple(g, subject, p, "B")
        self.assert_triple(g, subject, p, "C")

    def test_object_field_collapsed(self):
        subject = URIRef("http://api.nickswebsite.net/data#2")

        class S(RdfSerializer):
            field = RdfStringField(predicate="http://api.nickswebsite.net/ns/field")

        class M(object):
            def __init__(self):
                self.field = "Some Field"

        f = RdfObjectField(S, collapse=True)

        invalid_model = M()
        invalid_model.field = 3
        self.assertRaises(ValidationError, f.validate, invalid_model)

        valid_model = M()
        f.validate(valid_model)

        g = f.build_graph(valid_model, subject)
        self.assert_triple(g, subject, "http://api.nickswebsite.net/ns/field", "Some Field")

    def test_object_field_not_collapsed(self):
        subject = URIRef("http://api.nickswebsite.net/data#2")
        object_predicate = "http://api.nickswebsite.net/object-item"
        field_predicate = "http://api.nickswebsite.net/ns/field"

        class ModelSerializer(RdfSerializer):
            field = RdfStringField(predicate=field_predicate)

        class Model(object):
            def __init__(self):
                self.field = "Some Field"

        f = RdfObjectField(ModelSerializer, predicate=object_predicate, collapse=False)

        invalid_model = Model()
        invalid_model.field = 3
        self.assertRaises(ValidationError, f.validate, invalid_model)

        valid_model = Model()
        f.validate(valid_model)

        g = f.build_graph(valid_model, subject)
        self.assert_triple(g, subject, "http://api.nickswebsite.net/ns/field", "Some Field")

    def test_datetime_field(self):
        f = RdfDateTimeField("http://api.nickswebsite.net/ns/1")

        expected = datetime.datetime(2014, 2, 1, 3, 5)
        self.assertEqual(expected, f.render(expected))

        f.validate(expected)

        self.assertRaises(ValidationError, f.validate, "Some String")
        self.assertRaises(ValidationError, f.validate, 123)

    def test_date_field(self):
        f = RdfDateField("http://api.nickswebsite.net/ns/date")

        expected = datetime.date(2014, 2, 1)
        self.assertEqual(expected, f.render(expected))

        f.validate(expected)
        f.validate(datetime.datetime(2014, 2, 1, 2))

        result = f.render(datetime.datetime(2014, 2, 1, 2))
        self.assertEqual(datetime.date(2014, 2, 1), result)

        self.assertRaises(ValidationError, f.validate, "Some String")
        self.assertRaises(ValidationError, f.validate, 123)
        self.assertRaises(ValidationError, f.validate, True)

    def test_time_field(self):
        f = RdfTimeField("http://api.nickswebsite.net#dt")

        expected = datetime.time(2, 1, 3)
        self.assertEqual(expected, f.render(expected))

        f.validate(expected)

        self.assertRaises(ValidationError, f.validate, datetime.datetime(2013, 2, 11, 3))
        self.assertRaises(ValidationError, f.validate, "Some String")
        self.assertRaises(ValidationError, f.validate, True)
        self.assertRaises(ValidationError, f.validate, 123)
        self.assertRaises(ValidationError, f.validate, datetime.date(2012, 6, 12))

    def test_uuid_field(self):
        f = RdfUuidField("http://api.nickswebsite.net/ns/data-type")
        self.assertNotEqual("@id", f.datatype)

        expected = uuid.uuid4()
        self.assertEqual(str(expected), f.render(expected))

        f.validate(uuid.uuid4())
        f.validate(str(uuid.uuid4()))
        f.validate(uuid.uuid4().hex)

        self.assertRaises(ValidationError, f.validate, "xyz")
        self.assertRaises(ValidationError, f.validate, True)

        iri_field = RdfUuidField("http://api.nickswebsite.net/ns/data-type", iri=True)
        self.assertEqual(iri_field.datatype, "@id")

        test = "4e0b25c1-0792-4e7d-89b5-fe26460dff5b"
        self.assertEqual("urn:uuid:{}".format(test), iri_field.render(uuid.UUID(test)))

        # Make sure that the serializers will parse this correctly
        class ModelSerializer(RdfSerializer):
            f = RdfUuidField("http://api.nickswebsite.net/data#1", iri=True)

        class Model(object):
            def __init__(self):
                self.f = uuid.uuid4()

        m = Model()
        s = ModelSerializer(object=m)
        g = s.build_graph()
        t = get_triples(g, None, "http://api.nickswebsite.net/data#1", None)
        self.assertEqual(URIRef("urn:uuid:{}".format(m.f)), t[0][-1])
