"""This module holds the loader that imports jeff programs as jeff dialect IR."""

from pathlib import Path

from kirin import ir
from kirin.validation import ValidationSuite

import jeff as jf
from bloqade.jeff.errors import JeffImportError
from bloqade.jeff.dialects import kernel as jeff_kernel
from bloqade.jeff.analysis.validation import LinearityValidation, StructureValidation

from .lowering import JeffLowering


def load_jeff(source: str | Path | jf.JeffModule) -> ir.Method:
    """Import a jeff module and return its entry function as a kirin method.

    The loader imports every function that the entry function reaches.
    The jeff validation passes then check the result.
    """
    match source:
        case str() | Path():
            try:
                with open(source, "rb") as file:
                    raw = jf.schema.Module.read(file, traversal_limit_in_words=1 << 62)
                module = jf.JeffModule.from_encoding(raw)
            except OSError:
                raise
            except Exception as error:
                raise JeffImportError(
                    f"'{source}' is not a jeff module: {error}"
                ) from error
        case jf.JeffModule():
            module = source
        case _:
            raise TypeError(
                "load_jeff takes a path or a jeff module, and it got "
                f"{type(source).__name__}"
            )
    version = module.version
    major, minor = jf.schema.schemaVersionMajor, jf.schema.schemaVersionMinor
    if (
        version is None
        or version.major != major
        or (major == 0 and version.minor != minor)
    ):
        raise JeffImportError(
            f"this reader does not support schema version {version}. "
            f"It reads version {major}.{minor}.x."
        )
    try:
        entry = JeffLowering(jeff_kernel, module=module).method(module.entrypoint)
    except JeffImportError:
        raise
    except Exception as error:
        raise JeffImportError(f"malformed jeff module: {error}") from error
    passes = [StructureValidation, LinearityValidation]
    ValidationSuite(passes).validate(entry).raise_if_invalid()
    return entry
