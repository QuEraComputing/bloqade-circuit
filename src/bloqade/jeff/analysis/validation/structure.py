"""This module holds the analysis that checks the structure of jeff functions."""

from kirin import ir, interp
from kirin.lattice import EmptyLattice
from kirin.dialects import func, ssacfg
from kirin.analysis.forward import ForwardFrame

from bloqade.jeff.dialects import stmts, kernel

from .base import SHARED_KEY, Check

KEY = "validate.jeff.structure"


class StructureAnalysis(Check[EmptyLattice]):
    """An analysis that checks the statements, regions and types of jeff functions."""

    keys = (KEY, SHARED_KEY)
    lattice = EmptyLattice
    isolated = True

    def enter_function(self, code: ir.Statement) -> bool:
        """Check the body of the function `code` and run kirin's checks on it.

        If the analysis cannot run the body, the method returns False.
        """
        region = code.get_present_trait(ir.CallableStmtInterface).get_callable_region(
            code
        )
        if len(region.blocks) != 1:
            self.error(code, "a jeff function body must hold one block")
            return False
        try:
            code.verify()
            code.verify_type()
        except ir.ValidationError as error:
            self.add_validation_error(error.node, error)
        if not isinstance(region.blocks[0].last_stmt, stmts.Return):
            self.error(code, "a jeff function body must end in a jeff return")
            return False
        return super().enter_function(code)

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> interp.StatementResult[EmptyLattice]:
        """Report a foreign statement or a misplaced terminator."""
        if node.has_trait(ir.IsTerminator):
            _report_statements_after(self, node)
        if node.dialect not in kernel or node.dialect in (func.dialect, ssacfg.dialect):
            dialect = node.dialect.name if node.dialect else "?"
            self.error(
                node,
                f"statement '{node.name}' of dialect '{dialect}' "
                "is not a jeff statement",
            )
        return super().eval_fallback(frame, node)

    def operand_missing(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement, value: ir.SSAValue
    ) -> None:
        """Report an operand that the statement cannot read."""
        defining_block = None
        if isinstance(value, ir.ResultValue):
            defining_block = value.owner.parent_block
        elif isinstance(value, ir.BlockArgument):
            defining_block = value.block
        reading_block = frame.current_block
        if defining_block is None or reading_block in (None, defining_block):
            self.error(
                node, f"operand '{value}' has no definition that reaches this statement"
            )
        elif reading_block.is_ancestor(defining_block):
            self.error(
                node,
                "a statement reads a value from inside "
                f"'{getattr(defining_block.parent_stmt, 'name', '?')}'. "
                "Code outside a region can read only the results of the statement "
                "that owns the region.",
            )
        else:
            self.error(
                node,
                f"a block of '{getattr(reading_block.parent_stmt, 'name', '?')}' reads "
                "a value from outside the block. "
                "Each jeff function and region must be isolated.",
            )


def _report_statements_after(
    check: StructureAnalysis, terminator: ir.Statement
) -> None:
    """Report a terminator that another statement follows in its block."""
    block = terminator.parent_block
    if block is not None and terminator is not block.last_stmt:
        check.error(terminator, "a block has statements after its terminator")


@stmts.scf.dialect.register(key=KEY)
class _Scf(interp.MethodTable):
    """A method table that checks the position of each yield."""

    @interp.impl(stmts.Yield)
    def yield_(
        self,
        check: StructureAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: stmts.Yield,
    ) -> interp.YieldValue[EmptyLattice]:
        """Report statements after the yield, then end the region."""
        _report_statements_after(check, stmt)
        return interp.YieldValue(check.read(frame, stmt, stmt.values))
