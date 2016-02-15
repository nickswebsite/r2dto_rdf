import doctest
import glob
import sys
import unittest

try:
    import pep8
except ImportError:
    print("WARNING: pep8 not installed.  Style will not be checked and therefore your build may fail when integrated"
          "with the main branch.")
    pep8 = None

PEP8_EXCLUDES = ()

from tests.test_serializers import SerializerTests
from tests.test_r2dto_mappings import R2DtoMappingTests


if __name__ == "__main__":
    pep8_sources = glob.glob("**/*.py") + glob.glob("tests/*.py") + glob.glob("r2dto_rdf/*.py")
    pep8_sources = [f for f in pep8_sources if f not in PEP8_EXCLUDES]
    if pep8 is not None:
        sg = pep8.StyleGuide(max_line_length=120)
        res = sg.check_files(pep8_sources)
        if res.total_errors != 0:
            print("pep8 failed")
            # sys.exit(1)

    # doctest_ctx = {
    #     "Serializer": r2dto.Serializer,
    #     "fields": r2dto.fields,
    #     "ValidationError": r2dto.ValidationError,
    # }

    # results = doctest.testfile("../README.md", globs=doctest_ctx)
    # if results.failed != 0:
    #     sys.exit(1)
    unittest.main()
