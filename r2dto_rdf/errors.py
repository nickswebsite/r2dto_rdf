from __future__ import unicode_literals

from r2dto import ValidationError as R2DtoValidationError


class ValidationError(R2DtoValidationError):
    pass
