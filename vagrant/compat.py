"""
vagrant.compat
--------------

Python 2/3 compatiblity module.
"""

# std
import locale
import sys


PY2 = sys.version_info[0] == 2


def decode(value):
    """Decode binary data to text if needed (for Python 3).

    Use with the functions that return in Python 2 value of `str` type and for Python 3 encoded bytes.

    :param value: Encoded bytes for Python 3 and `str` for Python 2.
    :return: Value as a text.
    """
    return value.decode(locale.getpreferredencoding()) if not PY2 else value
