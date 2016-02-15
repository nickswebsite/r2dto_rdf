from __future__ import unicode_literals

import unittest

from rdflib import URIRef

from r2dto_rdf import ValidationError, RdfIriField, RdfStringField, RdfObjectField, RdfSetField, RdfSerializer, \
    RdfBooleanField, RdfIntegerField, RdfFloatField
from r2dto_rdf.fields import RdfDateTimeField
from r2dto_rdf.serializer import RdflibNamespaceManager

from tests.utils import RdflibTestCaseMixin


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

    def test_datetime_field(self):
        import datetime

        f = RdfDateTimeField("http://api.nws#1")

        expected = datetime.datetime(2014, 2, 1, 3, 5)
        self.assertEqual(expected, f.render(expected))

        f.validate(expected)

        self.assertRaises(ValidationError, f.validate, "Some String")
        self.assertRaises(ValidationError, f.validate, 123)

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
        s = URIRef("http://api.nickswebsite.net/data#1")
        p = "http://api.transparent.com/list-item"

        f = RdfSetField(RdfStringField(), predicate=p)

        # TODO this shouldn't need to happen.
        class S(object):
            namespace_manager = RdflibNamespaceManager()
        f.parent = S()

        f.validate(["A", "B", "C"])
        self.assertRaises(ValidationError, f.validate, ["A", 2, "C"])

        g = f.build_graph(["A", "B", "C"], s)
        self.assert_triple(g, s, p, "A")
        self.assert_triple(g, s, p, "B")
        self.assert_triple(g, s, p, "C")

    def test_object_field_collapsed(self):
        s = URIRef("http://api.nickswebsite.net/data#2")
        p = "http://api.transparent.com/object-item"

        class S(RdfSerializer):
            field = RdfStringField(predicate="http://api.transparent.com/ns/field")

        class M(object):
            def __init__(self):
                self.field = "Some Field"

        f = RdfObjectField(S, collapse=True)

        im = M()
        im.field = 3
        self.assertRaises(ValidationError, f.validate, im)

        m = M()
        f.validate(m)

        g = f.build_graph(m, s)
        self.assert_triple(g, s, "http://api.transparent.com/ns/field", "Some Field")

    def test_object_field_not_collapsed(self):
        s = URIRef("http://api.nickswebsite.net/data#2")
        p = "http://api.transparent.com/object-item"
        fp = "http://api.transparent.com/ns/field"

        class S(RdfSerializer):
            field = RdfStringField(predicate=fp)

        class M(object):
            def __init__(self):
                self.field = "Some Field"

        f = RdfObjectField(S, predicate=p, collapse=False)

        im = M()
        im.field = 3
        self.assertRaises(ValidationError, f.validate, im)

        m = M()
        f.validate(m)

        g = f.build_graph(m, s)
        self.assert_triple(g, s, "http://api.transparent.com/ns/field", "Some Field")