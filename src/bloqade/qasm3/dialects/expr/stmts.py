from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import func
from kirin.print.printer import Printer

from ._dialect import dialect

# QASM 3.0 arithmetic type variable
PyNum = types.TypeVar("PyNum", bound=types.Union(types.Int, types.Float))


@statement(dialect=dialect)
class ConstInt(ir.Statement):
    """IR Statement representing a constant integer value."""

    name = "constant.int"
    traits = frozenset({ir.Pure(), ir.ConstantLike(), lowering.FromPythonCall()})
    value: int = info.attribute(types.Int)
    result: ir.ResultValue = info.result(types.Int)

    def print_impl(self, printer: Printer) -> None:
        printer.print_name(self)
        printer.plain_print(" ")
        printer.plain_print(repr(self.value))
        with printer.rich(style="comment"):
            printer.plain_print(" : ")
            printer.print(self.result.type)


@statement(dialect=dialect)
class GateFunction(func.Function):
    """Special Function for qasm3 gate subroutine."""

    name = "gate.func"

    def print_impl(self, printer: Printer) -> None:
        with printer.rich(style="red"):
            printer.plain_print(self.name + " ")

        with printer.rich(style="cyan"):
            printer.plain_print(self.sym_name)

        self.signature.print_impl(printer)
        printer.plain_print(" ")
        self.body.print_impl(printer)

        with printer.rich(style="black"):
            printer.plain_print(f" // gate.func {self.sym_name}")


@statement(dialect=dialect)
class ConstFloat(ir.Statement):
    """IR Statement representing a constant float value."""

    name = "constant.float"
    traits = frozenset({ir.Pure(), ir.ConstantLike(), lowering.FromPythonCall()})
    value: float = info.attribute(types.Float)
    result: ir.ResultValue = info.result(types.Float)

    def print_impl(self, printer: Printer) -> None:
        printer.print_name(self)
        printer.plain_print(" ")
        printer.plain_print(repr(self.value))
        with printer.rich(style="comment"):
            printer.plain_print(" : ")
            printer.print(self.result.type)


@statement(dialect=dialect)
class ConstPI(ir.Statement):
    """The constant value of PI."""

    name = "constant.pi"
    traits = frozenset({ir.ConstantLike(), lowering.FromPythonCall()})
    result: ir.ResultValue = info.result(types.Float)

    def print_impl(self, printer: Printer) -> None:
        printer.print_name(self)
        printer.plain_print(" PI")
        with printer.rich(style="comment"):
            printer.plain_print(" : ")
            printer.print(self.result.type)


@statement(dialect=dialect)
class Neg(ir.Statement):
    """Negate a number."""

    name = "neg"
    traits = frozenset({lowering.FromPythonCall()})
    value: ir.SSAValue = info.argument(PyNum)
    result: ir.ResultValue = info.result(PyNum)


@statement(dialect=dialect)
class Add(ir.Statement):
    """Add two numbers."""

    name = "add"
    traits = frozenset({lowering.FromPythonCall()})
    lhs: ir.SSAValue = info.argument(PyNum)
    rhs: ir.SSAValue = info.argument(PyNum)
    result: ir.ResultValue = info.result(PyNum)


@statement(dialect=dialect)
class Sub(ir.Statement):
    """Subtract two numbers."""

    name = "sub"
    traits = frozenset({lowering.FromPythonCall()})
    lhs: ir.SSAValue = info.argument(PyNum)
    rhs: ir.SSAValue = info.argument(PyNum)
    result: ir.ResultValue = info.result(PyNum)


@statement(dialect=dialect)
class Mul(ir.Statement):
    """Multiply two numbers."""

    name = "mul"
    traits = frozenset({lowering.FromPythonCall()})
    lhs: ir.SSAValue = info.argument(PyNum)
    rhs: ir.SSAValue = info.argument(PyNum)
    result: ir.ResultValue = info.result(PyNum)


@statement(dialect=dialect)
class Div(ir.Statement):
    """Divide two numbers."""

    name = "div"
    traits = frozenset({lowering.FromPythonCall()})
    lhs: ir.SSAValue = info.argument(PyNum)
    rhs: ir.SSAValue = info.argument(PyNum)
    result: ir.ResultValue = info.result(PyNum)
