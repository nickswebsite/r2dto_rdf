from __future__ import unicode_literals

import uuid

import r2dto
from rdflib import Namespace, URIRef, BNode, Graph, Literal, RDF
from rdflib.term import Node

from r2dto_rdf.fields import RdfField, RdfIriField
from r2dto_rdf.errors import ValidationError


def split_prefix(raw, prefixes=None):
    prefixes = prefixes or ()
    if ":" in raw:
        prefix, postfix = raw.split(":", 1)
        if prefix in prefixes:
            return prefix, postfix
    return None, raw


class RdflibNamespaceManager(object):
    def __init__(self):
        self.namespaces = {}

    def bind(self, prefix, uri):
        ns = Namespace(uri)
        self.namespaces[prefix] = ns
        return ns

    def resolve_term(self, raw):
        prefix, postfix = split_prefix(raw, self.namespaces)
        if prefix:
            return self.namespaces[prefix][postfix]
        else:
            return URIRef(postfix)

    def __getitem__(self, item):
        return self.namespaces[item]

    def items(self):
        return self.namespaces.items()


class RdfSerializerMetaclass(type):
    def __new__(cls, name, bases, attrs):
        fields = []
        for k, v in attrs.items():
            if isinstance(v, RdfField):
                v.object_field_name = k
                fields.append(v)

        options = attrs.pop("Meta", None)
        if not options:
            class Meta:
                pass
            options = Meta

        if not hasattr(options, "rdf_subject"):
            options.rdf_subject = None
            options.rdf_subject_field = None

        if options.rdf_subject:
            if options.rdf_subject not in attrs:
                attrs[options.rdf_subject] = RdfIriField(required=True)
                attrs[options.rdf_subject].object_field_name = options.rdf_subject
                fields.append(attrs[options.rdf_subject])
            options.rdf_subject_field = attrs[options.rdf_subject]

        if not hasattr(options, "rdf_prefixes"):
            options.rdf_prefixes = {}

        if not hasattr(options, "rdf_type"):
            options.rdf_type = None

        namespace_manager = RdflibNamespaceManager()
        for k, v in options.rdf_prefixes.items():
            namespace_manager.bind(k, v)

        errors = []
        for field in fields:
            erm = field.get_configuration_errors()
            if erm:
                errors.append("{}.{}: {}".format(name, field.object_field_name, erm))

        if errors:
            raise ValueError("Configuration Error: {}".format("\n".join(errors)))

        new_class_attrs = {k: v for k, v in attrs.items() if not isinstance(v, RdfField)}
        new_class_attrs["fields"] = fields
        new_class_attrs["options"] = options
        new_class_attrs["namespace_manager"] = namespace_manager
        ret = super(RdfSerializerMetaclass, cls).__new__(cls, name, bases, new_class_attrs)
        for field in fields:
            field.parent = ret
        return ret


class BaseRdfSerializer(object):
    namespace_manager = None
    options = None
    fields = None

    def __init__(self, object=None, data=None):
        self.object = object
        self.data = data

    def validate(self):
        errors = []
        for field in self.fields:
            if field.required:
                if not hasattr(self.object, field.object_field_name):
                    errors.append("Field {} is missing from object.".format(field.object_field_name))
                elif not getattr(self.object, field.object_field_name):
                    errors.append("Field {} cannot be None.".format(field.object_field_name))

            if hasattr(self.object, field.object_field_name):
                data = getattr(self.object, field.object_field_name)
                try:
                    field.validate(data)
                except ValidationError as ex:
                    errors.extend(ex.errors)

                if field.validators:
                    validators = field.validators
                    if not hasattr(validators, "__iter__"):
                        validators = (validators,)

                    for validator in validators:
                        try:
                            validator(data)
                        except ValidationError as ex:
                            errors.extend(ex.errors)

        if errors:
            raise ValidationError(errors)

    def build_graph(self, subject=None):
        """
        Returns an list of lists of the form:
        [[subject, [(predicate_one, value_one), (predicate_two, value_two)], ...]]]]
        """
        if not subject:
            subject_field = self.options.rdf_subject_field
            if subject_field:
                subject_attr_data = getattr(self.object, subject_field.object_field_name)
                subject_iri = subject_field.render(subject_attr_data)
            else:
                subject_iri = "_:" + uuid.uuid4().hex
            subject_node = None
        else:
            if isinstance(subject, Node):
                subject_node = subject
            else:
                subject_node = None
            subject_field = None
            subject_iri = subject

        g = Graph()
        for k, v in self.namespace_manager.namespaces.items():
            g.bind(k, v)
        if subject_node is None:
            if subject_iri.startswith("_:"):
                subject_node = BNode(subject_iri)
            else:
                subject_node = URIRef(subject_iri)

        predicate_fields = [field for field in self.fields if field is not subject_field]
        for field in predicate_fields:
            obj = getattr(self.object, field.object_field_name)
            if hasattr(field, "build_graph"):
                if field.collapse:
                    subobject_graph = field.build_graph(obj, subject_node)
                else:
                    blank_node_name = "_:" + uuid.uuid4().hex
                    blank_node = BNode(blank_node_name)
                    subobject_graph = field.build_graph(obj, blank_node)
                    predicate = self.namespace_manager.resolve_term(field.predicate)
                    g.add((subject_node, predicate, blank_node))
                g += subobject_graph
            else:
                predicate = self.namespace_manager.resolve_term(field.predicate)
                raw_data = field.render(getattr(self.object, field.object_field_name))

                data_type = None
                if field.datatype and field.datatype[0] != "@":
                    data_type = self.namespace_manager.resolve_term(field.datatype)

                if field.datatype == "@id":
                    data = URIRef(raw_data)
                else:
                    data = Literal(raw_data, field.language, data_type)

                g.add((subject_node, predicate, data))
        if self.options.rdf_type:
            g.add((subject_node, RDF.type, self.namespace_manager.resolve_term(self.options.rdf_type)))

        return g


class RdfSerializer(r2dto.base.with_metaclass(RdfSerializerMetaclass, BaseRdfSerializer)):
    pass
