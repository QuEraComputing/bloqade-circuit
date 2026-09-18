"""This module holds the errors that the jeff package raises."""


class JeffImportError(Exception):
    """Signal that the loader cannot import a file or module as a jeff program."""
