"""This module holds the kirin dialects that represent the jeff exchange format.

The `jeff` extra installs `jeff-format`, which reads and writes `.jeff` files.
The dialects and the validation passes work without the extra.
"""

from typing import NoReturn

from . import dialects as dialects
from .types import (
    Wire as Wire,
    Qureg as Qureg,
    IntArray as IntArray,
    WireType as WireType,
    QuregType as QuregType,
    FloatArray as FloatArray,
    IntArrayType as IntArrayType,
    FloatArrayType as FloatArrayType,
)
from .errors import JeffImportError as JeffImportError
from .dialects import kernel as kernel

try:
    from .emit import EmitJeff as EmitJeff, emit_jeff as emit_jeff
    from .parse import load_jeff as load_jeff
except ImportError as _error:
    # Python deletes `_error` at the end of this block, so the stubs keep a copy.
    _jeff_import_error = _error
    _HINT = 'Install with: pip install "bloqade-circuit[jeff]"'

    def _emit_jeff(*args: object, **kwargs: object) -> NoReturn:
        """Raise an `ImportError` that tells the caller to install `jeff-format`."""
        raise ImportError(
            f"jeff-format is required to write jeff files. {_HINT}"
        ) from _jeff_import_error

    def _load_jeff(*args: object, **kwargs: object) -> NoReturn:
        """Raise an `ImportError` that tells the caller to install `jeff-format`."""
        raise ImportError(
            f"jeff-format is required to read jeff files. {_HINT}"
        ) from _jeff_import_error

    emit_jeff = _emit_jeff
    load_jeff = _load_jeff
