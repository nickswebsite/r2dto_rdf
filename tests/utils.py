from __future__ import unicode_literals

from rdflib import BNode, URIRef, Literal
from rdflib.term import Identifier

from pprint import pprint


def print_graph(g):
    print(g.serialize(format="turtle"))
    pprint(list(g))


def to_rdf_triples(s, p, o, datatype=None, language=None):
    if s is not None and not isinstance(s, Identifier):
        if s.startswith("_:"):
            s = BNode(s)
        else:
            s = URIRef(s)

    if p is not None and not isinstance(p, Identifier):
        p = URIRef(p)

    if isinstance(o, basestring):
        if o.startswith("_:"):
            o = BNode(o)
        elif "://" in o:
            o = URIRef(o)
        else:
            o = Literal(o, lang=language, datatype=datatype)

    if o is not None and not isinstance(o, Identifier):
        o = Literal(o, lang=language, datatype=datatype)

    return s, p, o


def get_triples(g, s, p, o, datatype=None, language=None):
    s, p, o = to_rdf_triples(s, p, o, datatype, language)
    return list(g.triples((s, p, o)))


class RdflibTestCaseMixin(object):
    def assert_uri_equal(self, uri, s):
        self.assertEqual(URIRef(uri), s)

    def assert_literal_equal(self, expected, literal, data_type=None, language=None):
        self.assertEqual(Literal(expected, lang=language, datatype=data_type), literal)

    def assert_triple(self, g, s, p, o, datatype=None, language=None):
        s, p, o = to_rdf_triples(s, p, o, datatype=datatype, language=language)
        self.assertIn((s, p, o), g)
