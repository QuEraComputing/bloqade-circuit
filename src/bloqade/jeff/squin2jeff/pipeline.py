"""Convert squin through verified wire values before rewriting them to Jeff."""

from dataclasses import dataclass

from kirin import ir
from kirin.rewrite import Walk, Chain, Fixpoint, DeadCodeElimination
from kirin.dialects import py
from kirin.validation import ValidationSuite
from kirin.dialects.py import slice as py_slice
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.ir.exception import ValidationErrorGroup
from kirin.dialects.ilist import stmts as ilist_stmts

from bloqade.jeff.dialects import kernel as jeff_kernel
from bloqade.squin.wire.group import kernel as wire_kernel, reference_kernel
from bloqade.squin.wire.stmts import Operation
from bloqade.squin.wire.errors import WireConversionError
from bloqade.squin.wire.ownership import KEY as OWNED
from bloqade.jeff.analysis.validation import LinearityValidation, StructureValidation
from bloqade.squin.passes.wire_target import ConversionTarget
from bloqade.squin.rewrite.wire.driver import reachable
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.analysis.validation.wire import WireValidation

from .isolate import IsolateRegions
from .py2jeff import Classical
from .quantum import Quantum
from .scf2jeff import ControlFlow
from .functions import Functions


@dataclass
class WireToJeff:
    """Rewrite complete wire squin to Jeff and verify every Jeff function.

    Each rule replaces one statement with its Jeff form and keeps no state. The walk
    visits a statement before its regions and each block in order. So every operand
    already holds its Jeff value and type when a rule reads it.
    """

    def emit(self, method: ir.Method) -> ir.Method:
        """Return the Jeff copy of `method`, and leave `method` and its callees as they are."""
        if method.dialects is not wire_kernel:
            raise ValueError("WireToJeff expects squin.wire kernel dialects.")
        methods = reachable(method)
        for callee in methods:
            if illegal := ConversionTarget.check(callee):
                raise WireConversionError(
                    "Jeff requires complete wire conversion: "
                    f"{', '.join(sorted(set(illegal)))}.",
                    callee.code,
                )
            WireValidation().check(callee)
        copies = {
            source: source.similar(jeff_kernel.union(wire_kernel)) for source in methods
        }
        rules = Chain(
            Functions(copies), ControlFlow(), Quantum(), Classical(), Unsupported()
        )
        cleanup = Fixpoint(Walk(DeadCodeElimination()))
        # `reachable` lists each callee before its callers.
        for copy in copies.values():
            copy.code.attributes.pop(OWNED, None)
            try:
                cleanup.rewrite(copy.code)
                Walk(rules, region_first=True).rewrite(copy.code)
                cleanup.rewrite(copy.code)
            except ir.ValidationError as error:
                raise ValidationErrorGroup(
                    f"Jeff emission failed for '{method.sym_name}'.", [error]
                ) from error
            copy.dialects = jeff_kernel
            IsolateRegions(copy.dialects)(copy)
            ValidationSuite([StructureValidation, LinearityValidation]).validate(
                copy
            ).raise_if_invalid()
        return copies[method]


KEPT = (
    py.Constant,
    py.tuple.New,
    py.indexing.GetItem,
    ilist_stmts.Range,
    py_slice.Slice,
)
"""The statements that the rules can leave for dead-code elimination to remove.

A range, a slice and the constant None have no Jeff value, and a tuple has fields
that later rules read.
"""


class Unsupported(RewriteRule):
    """Reject a live statement that no earlier rule replaced and that has no Jeff form.

    The rule runs last in the chain on each statement. A replaced statement has
    already left its block. Dead-code elimination runs before the rules, so every
    statement that remains has a use.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Raise an error for `node` if it stays in its block without a Jeff form."""
        if (
            node.parent_block is None
            or node.dialect in jeff_kernel.data
            or isinstance(node, KEPT)
        ):
            return RewriteResult()
        name = node.label if isinstance(node, Operation) else node.name
        raise ir.ValidationError(node, f"Jeff has no form for '{name}'.")


@dataclass
class SquinToJeff:
    """Convert a squin kernel to wire squin, then emit Jeff directly from those wires."""

    def emit(self, method: ir.Method) -> ir.Method:
        """Return verified Jeff while preserving the source kernel and its callees."""
        if not method.dialects.data <= reference_kernel.data:
            raise ValueError(
                "SquinToJeff expects squin.kernel or native kernel dialects."
            )
        try:
            wired = SquinToWire().emit(method)
        except WireConversionError as error:
            raise ValidationErrorGroup(
                f"SquinToJeff cannot convert '{method.sym_name}'.", [error]
            ) from error
        return WireToJeff().emit(wired)
