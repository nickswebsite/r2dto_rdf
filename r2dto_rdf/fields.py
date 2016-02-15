import urlparse
import uuid

import r2dto
from r2dto import ValidationError
import rdflib


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
