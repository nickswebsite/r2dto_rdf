from __future__ import unicode_literals

import unittest

import r2dto
from r2dto.base import ValidationError, InvalidTypeValidationError
import urlparse
import urllib
import uuid
import rdflib
from tests.utils import print_graph


def is_iri(iri):
    p = urlparse.urlparse(iri)
    return bool(p.scheme) and bool(p.netloc)


class RdfField(object):
    datatype = None

    def __init__(self, predicate, required, language=None):
        self.predicate = predicate
        self.required = required
        self.object_field_name = None
        self.language = language
        self.parent = None

    def get_configuration_errors(self):
        if not self.predicate:
            return "A predicate MUST be provided."

    def clean(self, data):
        return data

    def render(self, obj):
        return obj

    def validate(self, obj):
        pass


class RdfIriField(RdfField):
    datatype = "@id"

    def __init__(self, predicate=None, required=False, validators=None):
        self.string_field = r2dto.fields.StringField(validators=validators)
        super(RdfIriField, self).__init__(predicate, required)

    def get_configuration_errors(self):
        pass

    def render(self, obj):
        return obj

    def validate(self, obj):
        data = self.string_field.object_to_data(obj)
        if not is_iri(data):
            raise ValidationError(["{} is not an IRI".format(self.object_field_name)])

    @property
    def validators(self):
        return self.string_field.validators

    @validators.setter
    def validators(self, item):
        self.string_field.validators = item


class RdfStringField(RdfField):
    def __init__(self, predicate=None, required=False, validators=None, datatype=None, language=None):
        super(RdfStringField, self).__init__(predicate, required, language=language)
        self.string_field = r2dto.fields.StringField(validators=validators)
        self.datatype = datatype

    def validate(self, obj):
        self.string_field.object_to_data(obj)

    @property
    def validators(self):
        return self.string_field.validators

    @validators.setter
    def validators(self, item):
        self.string_field.validators = item


class RdfObjectField(RdfField):
    def __init__(self, serializer_class, predicate=None, collapse=False, required=False, validators=None):
        super(RdfObjectField, self).__init__(predicate, required)
        self.serializer_class = serializer_class
        self.collapse = collapse
        self.predicate = predicate
        self.validators = validators

    def get_configuration_errors(self):
        if not self.collapse and not self.predicate:
            return "If RdfObjectField needs a predicate if not in collapse mode."
        if not hasattr(self.serializer_class, "validate"):
            return "serializer_class MUST have a 'validate' attribute."
        if not hasattr(self.serializer_class, "build_graph"):
            return "serializer_class MUST have a 'build_graph' attribute."

    def validate(self, obj):
        s = self.serializer_class(object=obj)
        s.validate()

    def build_graph(self, obj, subject):
        s = self.serializer_class(object=obj)
        return s.build_graph(subject)


class RdfSetField(RdfField):
    def __init__(self, allowed_type, predicate=None, collapse=True, required=False, validators=None):
        super(RdfSetField, self).__init__(predicate, required)
        self.predicate = predicate
        self.collapse = collapse
        self.validators = validators or ()
        self.allowed_type = allowed_type

        if isinstance(self.allowed_type, RdfObjectField):
            self.allowed_type.predicate = "@"

    def get_configuration_errors(self):
        if not self.allowed_type:
            return "RdfSetFields MUST have an 'allowed_type'"
        if not hasattr(self.allowed_type, "render") and not hasattr(self.allowed_type, "build_graph"):
            return "RdfSetFields.allowed_type must have either a 'render' field or a 'build_graph' field"

    def validate(self, obj):
        errors = []
        for item_i, item in enumerate(obj):
            try:
                self.allowed_type.validate(item)
            except ValidationError as ex:
                field_path = str(self.parent)
                errors.append("{}.{}[{}] error processing".format(field_path, self.object_field_name),)
                errors.extend(ex.errors)

        if errors:
            raise ValidationError(errors)

    def build_graph(self, obj, subject):
        if not subject:
            subject_node = rdflib.BNode("_:" + uuid.uuid4().hex)
        else:
            subject_node = subject

        g = rdflib.Graph()
        field = self.allowed_type
        for item in obj:
            if hasattr(field, "build_graph"):
                if field.collapse:
                    subobject_graph = field.build_graph(item, subject_node)
                else:
                    blank_node_name = "_:" + uuid.uuid4().hex
                    blank_node = rdflib.BNode(blank_node_name)
                    subobject_graph = field.build_graph(item, blank_node)
                    predicate = self.parent.namespace_manager.resolve_term(self.predicate)
                    g.add((subject_node, predicate, blank_node))
                g += subobject_graph
            else:
                predicate = self.parent.namespace_manager.resolve_term(self.predicate)
                data_type = None
                if field.datatype:
                    data_type = self.parent.namespace_manager.resolve_term(field.datatype)

                raw_data = field.render(item)
                data = rdflib.Literal(raw_data, field.language, data_type)
                g.add((subject, predicate, data))

        return g


def split_prefix(raw, prefixes=None):
    prefixes = prefixes or ()
    if ":" in raw:
        prefix, postfix = raw.split(":", 1)
        if prefix in prefixes:
            return prefix, postfix
    return None, raw


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


class RdflibNamespaceManager(object):
    def __init__(self):
        self.namespaces = {}

    def bind(self, prefix, uri):
        ns = rdflib.Namespace(uri)
        self.namespaces[prefix] = ns
        return ns

    def resolve_term(self, raw):
        prefix, postfix = split_prefix(raw, self.namespaces)
        if prefix:
            return self.namespaces[prefix][postfix]
        else:
            return rdflib.URIRef(postfix)

    def __getitem__(self, item):
        return self.namespaces[item]

    def items(self):
        return self.namespaces.items()


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
        self.validate()

        if not subject:
            subject_field = self.options.rdf_subject_field
            if subject_field:
                subject_attr_data = getattr(self.object, subject_field.object_field_name)
                subject_iri = subject_field.render(subject_attr_data)
            else:
                subject_iri = "_:" + uuid.uuid4().hex
        else:
            subject_field = None
            subject_iri = subject

        g = rdflib.Graph()
        for k, v in self.namespace_manager.namespaces.items():
            g.bind(k, v)

        if subject_iri.startswith("_:"):
            subject_node = rdflib.BNode(subject_iri)
        else:
            subject_node = rdflib.URIRef(subject_iri)

        predicate_fields = [field for field in self.fields if field is not subject_field]
        for field in predicate_fields:
            obj = getattr(self.object, field.object_field_name)
            if hasattr(field, "build_graph"):
                if field.collapse:
                    subobject_graph = field.build_graph(obj, subject_node)
                else:
                    blank_node_name = "_:" + uuid.uuid4().hex
                    blank_node = rdflib.BNode(blank_node_name)
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
                    data = rdflib.URIRef(raw_data)
                else:
                    data = rdflib.Literal(raw_data, field.language, data_type)

                g.add((subject_node, predicate, data))

        return g

    def term_to_uri_ref(self, term, namespaces):
        prefix, postfix = self.split_prefix(term)
        return namespaces[prefix][postfix]

    def split_prefix(self, raw):
        return split_prefix(raw, self.options.rdf_prefixes)


class RdfSerializer(r2dto.base.with_metaclass(RdfSerializerMetaclass, BaseRdfSerializer)):
    pass


class FieldTypeMappingError(ValueError):
    def __init__(self, type_from):
        self.type_from = type_from
        super(FieldTypeMappingError, self).__init__("Unable to map field of type {}".format(self.type_from))


def from_string_field(field, predicate):
    ret = RdfStringField(predicate=predicate, required=field.required, validators=field.validators)
    return ret


def from_list_field(field, predicate):
    if len(field.allowed_types) > 1:
        raise ValueError("Only single types are allowed for list fields at this time. :(")
    type_from = field.allowed_types[0]
    if type_from.__class__ not in FIELD_MAP:
        raise FieldTypeMappingError(type_from.__class__)
    type_to = FIELD_MAP[type_from.__class__](type_from, None)
    ret = RdfSetField(type_to,
                      predicate=predicate,
                      required=field.required,
                      validators=field.validators)
    return ret


def from_object_field(field, predicate):
    assert isinstance(field, r2dto.fields.ObjectField)
    s = create_rdf_serializer_from_r2dto_serializer(field.serializer_class)

    if predicate == "@collapse":
        ret = RdfObjectField(s, collapse=True, required=field.required, validators=field.validators)
    else:
        ret = RdfObjectField(s, predicate=predicate, required=field.required, validators=field.validators)

    return ret


FIELD_MAP = {
    r2dto.fields.StringField: from_string_field,
    r2dto.fields.ListField: from_list_field,
    r2dto.fields.ObjectField: from_object_field,
}


class BaseRdfR2DtoSerializer(BaseRdfSerializer):
    pass


def create_rdf_serializer_from_r2dto_serializer(serializer_class):
    options = serializer_class.options
    if not options:
        raise ValueError("Meta class MUST be defined.")
    if not hasattr(options, "rdf_subject"):
        options.rdf_subject = None

    rdf = getattr(serializer_class, "Rdf", None)
    if not rdf:
        raise ValueError("An Rdf class MUST be defined on the serializer.")

    overrides = {}
    for name, attr in vars(rdf).items():
        if isinstance(attr, RdfField):
            overrides[name] = attr

    rdf_fields = []
    for field in serializer_class.fields:
        if field.object_field_name not in overrides:
            if field.object_field_name == options.rdf_subject:
                rdf_field = RdfIriField()
                rdf_field.object_field_name = options.rdf_subject
                rdf_fields.append(rdf_field)
            elif field.__class__ in FIELD_MAP:
                predicate = getattr(rdf, field.object_field_name, None)
                rdf_field = FIELD_MAP[field.__class__](field, predicate)
                rdf_field.object_field_name = field.object_field_name
                rdf_fields.append(rdf_field)
            else:
                raise FieldTypeMappingError(field.__class__)

    def predicate_satisfied(field):
        if field.predicate is None:
            if hasattr(field, "collapse") and not field.collapse:
                return False
        return True

    non_predicate_fields = [field for field in rdf_fields if not predicate_satisfied(field) and
                            field.object_field_name != options.rdf_subject]
    if non_predicate_fields:
        raise ValueError(
                "The following fields don't have predicates: {}".format(
                        ", ".join([f.object_field_name for f in non_predicate_fields])
                )
        )

    attrs = {
        "Meta": options,
    }
    for field in rdf_fields:
        attrs[field.object_field_name] = field
    attrs.update(overrides)
    return RdfSerializerMetaclass(b"Rdf" + serializer_class.__name__, (RdfSerializer,), attrs)
