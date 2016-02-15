import rdflib


def print_graph(g):
    from pprint import pprint
    print(g.serialize(format="turtle"))
    pprint(list(g))


def to_rdf_triples(s, p, o, datatype=None, language=None):
    if s is not None and not isinstance(s, rdflib.term.Identifier):
        if s.startswith("_:"):
            s = rdflib.BNode(s)
        else:
            s = rdflib.URIRef(s)

    if p is not None and not isinstance(p, rdflib.term.Identifier):
        p = rdflib.URIRef(p)

    if isinstance(o, basestring):
        if o.startswith("_:"):
            o = rdflib.BNode(o)
        elif "://" in o:
            o = rdflib.URIRef(o)
        else:
            o = rdflib.Literal(o, lang=language, datatype=datatype)

    if o is not None and not isinstance(o, rdflib.term.Identifier):
        o = rdflib.Literal(o, lang=language, datatype=datatype)

    return s, p, o


def get_triples(g, s, p, o, datatype=None, language=None):
    s, p, o = to_rdf_triples(s, p, o, datatype, language)
    return list(g.triples((s, p, o)))


class RdflibTestCaseMixin(object):
    def assert_uri_equal(self, uri, s):
        self.assertEqual(rdflib.URIRef(uri), s)

    def assert_literal_equal(self, expected, literal, data_type=None, language=None):
        self.assertEqual(rdflib.Literal(expected, lang=language, datatype=data_type), literal)

    def assert_triple(self, g, s, p, o, datatype=None, language=None):
        s, p, o = to_rdf_triples(s, p, o, datatype=datatype, language=language)
        self.assertIn((s, p, o), g)
