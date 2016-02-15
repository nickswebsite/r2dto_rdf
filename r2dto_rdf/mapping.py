from __future__ import unicode_literals

import r2dto

from r2dto_rdf.serializer import RdfSerializerMetaclass, RdfSerializer
from r2dto_rdf.fields import RdfField, RdfIriField, RdfObjectField, RdfStringField, RdfSetField


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


def predicate_satisfied(field):
    if field.predicate is None:
        if hasattr(field, "collapse") and not field.collapse:
            return False
    return True


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
    # Cast 'Rdf' prefix to string to make it compatible with both python 2 and 3
    return RdfSerializerMetaclass(str("Rdf") + serializer_class.__name__, (RdfSerializer,), attrs)
