from __future__ import unicode_literals

import datetime
try:
    import urlparse
except ImportError:
    from urllib import parse as urlparse
import uuid

import r2dto
from rdflib import Graph, BNode, Literal

from r2dto_rdf.errors import ValidationError


def is_iri(iri):
    p = urlparse.urlparse(iri)
    return bool(p.scheme) and bool(p.netloc)


class RdfField(object):
    datatype = None

    def __init__(self, predicate, required, datatype=None, language=None, validators=None):
        self.predicate = predicate
        self.required = required
        self.object_field_name = None
        self.language = language
        self.parent = None
        self.validators = validators or ()
        if datatype:
            self.datatype = datatype

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
        super(RdfIriField, self).__init__(predicate, required, validators=validators)

    def get_configuration_errors(self):
        pass

    def render(self, obj):
        return obj

    def validate(self, obj):
        data = self.string_field.object_to_data(obj)
        if not is_iri(data):
            raise ValidationError(["{} is not an IRI".format(self.object_field_name)])


class RdfStringField(RdfField):
    def __init__(self, predicate=None, required=False, validators=None, datatype=None, language=None):
        super(RdfStringField, self).__init__(predicate, required, datatype=datatype,
                                             language=language, validators=validators)
        self.string_field = r2dto.fields.StringField(validators=validators)

    def validate(self, obj):
        try:
            self.string_field.object_to_data(obj)
        except r2dto.InvalidTypeValidationError as ex:
            raise ValidationError(ex.errors)


class RdfBooleanField(RdfField):
    def __init__(self, predicate, required=False):
        self.boolean_field = r2dto.fields.BooleanField(required=required)
        super(RdfBooleanField, self).__init__(predicate, required)

    def validate(self, obj):
        try:
            self.boolean_field.object_to_data(obj)
        except r2dto.InvalidTypeValidationError as ex:
            raise ValidationError(ex.errors)


class RdfIntegerField(RdfField):
    def __init__(self, predicate, required=False, validators=None, datatype=None):
        self.integer_field = r2dto.fields.IntegerField()
        super(RdfIntegerField, self).__init__(predicate, required, datatype)

    def validate(self, obj):
        if isinstance(obj, bool):
            raise ValidationError("{} must be a {}.  Got {}.".format(self.object_field_name, "int", type(obj)))
        try:
            self.integer_field.object_to_data(obj)
        except r2dto.InvalidTypeValidationError as ex:
            raise ValidationError(ex.errors)


class RdfFloatField(RdfField):
    def __init__(self, predicate, required=False, validators=None, datatype=None):
        self.float_field = r2dto.fields.FloatField(required=required, validators=validators)
        super(RdfFloatField, self).__init__(predicate, required, datatype)

    def validate(self, obj):
        try:
            self.float_field.object_to_data(obj)
        except r2dto.InvalidTypeValidationError as ex:
            raise ValidationError(ex.errors)


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
                errors.append("{}.{}[{}] error processing".format(field_path, self.object_field_name, item_i),)
                errors.extend(ex.errors)

        if errors:
            raise ValidationError(errors)

    def build_graph(self, obj, subject):
        if not subject:
            subject_node = BNode(uuid.uuid4().hex)
        else:
            subject_node = subject

        g = Graph()
        field = self.allowed_type
        for item in obj:
            if hasattr(field, "build_graph"):
                if field.collapse:
                    subobject_graph = field.build_graph(item, subject_node)
                else:
                    blank_node_name = uuid.uuid4().hex
                    blank_node = BNode(blank_node_name)
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
                data = Literal(raw_data, field.language, data_type)
                g.add((subject_node, predicate, data))

        return g


class RdfDateTimeField(RdfField):
    datatype = "http://www.w3.org/2001/XMLSchema#dateTime"

    def __init__(self, predicate, required=False, validators=None):
        super(RdfDateTimeField, self).__init__(predicate, required, validators=validators)
        self.datetime_field = r2dto.fields.DateTimeField(validators=validators)

    def validate(self, obj):
        try:
            self.datetime_field.object_to_data(obj)
        except r2dto.InvalidTypeValidationError as ex:
            raise ValidationError(ex.errors)


class RdfDateField(RdfField):
    datatype = "http://www.w3.org/2001/XMLSchema#date"

    def __init__(self, predicate, required=False, validators=None):
        super(RdfDateField, self).__init__(predicate, required, validators=validators)
        self.date_field = r2dto.fields.DateField(validators=validators)

    def validate(self, obj):
        try:
            self.date_field.object_to_data(obj)
        except r2dto.InvalidTypeValidationError as ex:
            raise ValidationError(ex.errors)

    def render(self, obj):
        return datetime.date(*obj.timetuple()[:3])


class RdfTimeField(RdfField):
    datatype = "http://www.w3.org/2001/XMLSchema#time"

    def __init__(self, predicate, required=False, validators=None):
        super(RdfTimeField, self).__init__(predicate, required, validators=validators)
        self.time_field = r2dto.fields.TimeField()

    def validate(self, obj):
        try:
            self.time_field.object_to_data(obj)
        except r2dto.InvalidTypeValidationError as ex:
            raise ValidationError(ex.errors)


class RdfUuidField(RdfField):
    def __init__(self, predicate, required=False, validators=None, iri=False):
        super(RdfUuidField, self).__init__(predicate, required, validators=validators)
        self.iri = iri
        if iri:
            self.datatype = "@id"

    def validate(self, obj):
        if not isinstance(obj, uuid.UUID):
            try:
                uuid.UUID(str(obj))
            except ValueError:
                raise ValidationError("{} is expected to be a UUID, got {}".format(self.object_field_name, type(obj)))

    def render(self, obj):
        if self.iri:
            return "urn:uuid:{}".format(str(obj))
        else:
            return str(obj)
