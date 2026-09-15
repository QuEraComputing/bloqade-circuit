"""This module holds the errors that the jeff package raises."""

from kirin.lowering import BuildError


class JeffImportError(BuildError):
    """Signal that the loader cannot import a file or module as a jeff program."""
