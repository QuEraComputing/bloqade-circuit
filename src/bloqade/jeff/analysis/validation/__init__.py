"""This package holds the validation passes for jeff IR."""

from .passes import (
    LinearityValidation as LinearityValidation,
    StructureValidation as StructureValidation,
)
from .to_squin import JeffToSquinValidation as JeffToSquinValidation
