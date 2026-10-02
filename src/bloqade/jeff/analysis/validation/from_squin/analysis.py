"""This module holds the validation pass for squin code that jeff cannot express."""

# The squin gate statements and the kirin `py` statements derive from base classes
# that a bare `@statement` decorates, which pyright reads as functions. A rule that
# stacks `interp.impl` for several of them then fails the argument check.
# pyright: reportArgumentType=false

from typing import Any
from functools import cached_property
from dataclasses import field, dataclass
from collections.abc import Mapping, Sequence

from kirin import ir, types, interp
from kirin.lattice import EmptyLattice
from kirin.dialects import py, scf, func, math, ilist
from kirin.validation import ValidationPass
from kirin.dialects.py import len as py_len
from kirin.interp.table import BoundedDef
from kirin.dialects.math import stmts as math_stmts
from kirin.analysis.forward import ForwardFrame

from bloqade.qubit import stmts as qubit_stmts
from bloqade.constants import constant_int
from bloqade.jeff.forms import (
    GATES,
    SWAPPED,
    EMIT_KEY,
    FLOAT_BINARY,
    GATE_KERNELS,
    QUBIT_KERNELS,
    is_library,
    loop_range,
)
from bloqade.squin.gate import stmts as gate_stmts
from bloqade.analysis.reference import (
    Ref,
    Slot,
    Whole,
    Members,
    Unknown,
    Register,
    Untracked,
    positions,
)
from bloqade.jeff.dialects.stmts.call import declared_outputs
from bloqade.squin.analysis.reference import QubitReferenceAnalysis

from ..base import Check

KEY = "jeff.from_squin"
"""The registry key of the rules that refuse what jeff cannot express."""


def _number_or_list(item: object) -> bool:
    """Return True if `item` is a number, a bit, or a list of them."""
    if isinstance(item, ilist.IList):
        return all(isinstance(member, (bool, int, float)) for member in item.data)
    return isinstance(item, (bool, int, float))


def _listed(kind: types.TypeAttribute) -> bool:
    """Return True if a value of type `kind` is a tuple, which jeff has no value for."""
    return not kind.is_subseteq(types.Bottom) and kind.is_subseteq(types.Tuple)


@dataclass
class SquinToJeffAnalysis(Check[EmptyLattice]):
    """An analysis that reports each construct of one squin kernel that jeff cannot express.

    The analysis checks a call from the caller's side. The callee needs its own run.
    """

    keys = (KEY,)
    lattice = EmptyLattice
    refs: Mapping[ir.SSAValue, Ref] = field(kw_only=True)
    """The reference of each value of the kernel, from `QubitReferenceAnalysis`."""

    @cached_property
    def analysis(self) -> QubitReferenceAnalysis:
        """Return a reference analysis, whose `items` finds the slots of a register."""
        return QubitReferenceAnalysis(self.dialects)

    @cached_property
    def emitted(self) -> Mapping[interp.Signature, BoundedDef]:
        """Return the rules of the emitter, which say which statements have a jeff form."""
        return self.dialects.registry.interpreter(keys=(EMIT_KEY,))

    def enter_function(self, code: ir.Statement) -> bool:
        """Return True if the body of `code` is one block that ends in a return.

        Any other body is refused, because the emitter fills one jeff block.
        """
        blocks = (
            code.get_present_trait(ir.CallableStmtInterface)
            .get_callable_region(code)
            .blocks
        )
        output = code.get_present_trait(ir.HasSignature).get_signature(code).output
        if output.is_subseteq(types.Bottom):
            self.refuse(
                code,
                "a return type that squin's type inference left as `Bottom`, such "
                "as a measured list or an annotation that disagrees with the body",
            )
        if len(blocks) == 1 and isinstance(blocks[0].last_stmt, func.Return):
            return True
        self.refuse(
            code, "a function whose body is not one block that ends in a return"
        )
        return False

    def refuse(self, node: ir.Statement, message: str) -> None:
        """Record that jeff cannot express `node`."""
        self.add_validation_error(node, ir.ValidationError(node, message))

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> interp.StatementResult[EmptyLattice]:
        """Refuse a statement that the emitter has no rule for, or a list operand.

        A statement without a rule of its own maps each operand to one jeff scalar,
        so a list or tuple operand has no place. An alias, a tuple and a length
        take a list or a tuple as they are. The operator rules call this method
        last, so that their statements get these checks too.
        """
        if interp.Signature(type(node)) not in self.emitted:
            self.refuse(node, f"jeff has no form for '{node.name}'")
        elif node.results and isinstance(
            ref := self.refs.get(node.results[0]), Unknown
        ):
            self.refuse(node, ref.reason)
        elif not isinstance(node, (py.assign.Alias, py.tuple.New, py_len.Len)) and not (
            node.results and isinstance(self.refs.get(node.results[0]), Members)
        ):
            for arg in node.args:
                if _listed(arg.type) or arg.type.is_subseteq(ilist.IListType):
                    self.refuse(
                        node, f"a value of type {arg.type} passed to '{node.name}'"
                    )
        return self.accept(frame, node)

    def accept(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> interp.StatementResult[EmptyLattice]:
        """Read the operands of a checked statement and give its results lattice top."""
        return super().eval_fallback(frame, node)

    def qubit(self, node: ir.Statement, ref: Ref) -> bool:
        """Return True if `ref` names one qubit that a wire can carry, else refuse."""
        match ref:
            case Whole() | Slot():
                return True
            case Unknown(reason):
                self.refuse(node, reason)
            case _:
                self.refuse(node, "a qubit that no wire carries")
        return False

    def items(self, node: ir.Statement, value: ir.SSAValue) -> Sequence[Ref]:
        """Return the qubits that `value` holds, or refuse and return none.

        `value` holds one qubit, a literal list of qubits, or a register of static
        length, whose slots are its qubits.
        """
        ref = self.refs[value]
        if isinstance(ref, Unknown):
            self.refuse(node, ref.reason)
            return ()
        items = self.analysis.items(ref)
        if items is None:
            self.refuse(
                node,
                "qubits that are not one, a literal list or a register of known length",
            )
            return ()
        return items if all(self.qubit(node, item) for item in items) else ()

    def gate(self, node: ir.Statement, operands: Sequence[ir.SSAValue]) -> None:
        """Check the qubit operands of a gate: lists of one length, distinct groups."""
        lists = [self.items(node, value) for value in operands]
        if all(lists) and len({len(items) for items in lists}) == 1:
            for group in zip(*lists, strict=True):
                self.distinct(node, group)
        elif all(lists):
            self.refuse(node, "qubit lists of different lengths")

    def negated(self, node: ir.Statement, value: ir.SSAValue) -> None:
        """Refuse `node` if it negates a list of bits whose length is not static.

        Jeff negates one bit at a time, so the emitter needs the length.
        """
        kind = value.type
        if kind.is_subseteq(ilist.IListType) and not (
            isinstance(kind, types.Generic) and isinstance(kind.vars[1], types.Literal)
        ):
            self.refuse(node, "a negation of a list of bits of unknown length")

    def distinct(self, node: ir.Statement, refs: Sequence[Ref]) -> None:
        """Refuse `node` if it takes one qubit twice."""
        if len(set(refs)) < len(refs):
            match node:
                case func.Invoke(callee=callee):
                    name = callee.sym_name
                case _:
                    name = node.name
            self.refuse(node, f"'{name}' takes one qubit twice")

    def regions(
        self, frame: ForwardFrame[EmptyLattice], stmt: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        """Refuse a result of `stmt` that jeff cannot carry, then run each region once."""
        for result in stmt.results:
            if isinstance(ref := self.refs[result], Unknown):
                self.refuse(stmt, ref.reason)
            elif not isinstance(ref, (Whole, Register)) and _listed(result.type):
                self.refuse(stmt, f"a result of type {result.type}")
        return self.run_regions(frame, stmt)


@gate_stmts.dialect.register(key=KEY)
class _Gates(interp.MethodTable):
    """A method table that refuses gates that jeff cannot apply to wires."""

    @interp.impl(gate_stmts.X)
    @interp.impl(gate_stmts.Y)
    @interp.impl(gate_stmts.Z)
    @interp.impl(gate_stmts.H)
    @interp.impl(gate_stmts.S)
    @interp.impl(gate_stmts.T)
    @interp.impl(gate_stmts.SqrtX)
    @interp.impl(gate_stmts.SqrtY)
    @interp.impl(gate_stmts.Rx)
    @interp.impl(gate_stmts.Ry)
    @interp.impl(gate_stmts.Rz)
    @interp.impl(gate_stmts.U3)
    @interp.impl(gate_stmts.CX)
    @interp.impl(gate_stmts.CY)
    @interp.impl(gate_stmts.CZ)
    @interp.impl(gate_stmts.Swap)
    @interp.impl(gate_stmts.CCZ)
    def gate(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: ir.Statement,
    ) -> interp.StatementResult[EmptyLattice]:
        """Check the qubit operands of a gate statement."""
        check.gate(stmt, stmt.args[GATES[type(stmt)].angles :])
        return check.accept(frame, stmt)


@qubit_stmts.dialect.register(key=KEY)
class _Qubits(interp.MethodTable):
    """A method table that refuses measurements and resets of qubits without wires."""

    @interp.impl(qubit_stmts.Measure)
    @interp.impl(qubit_stmts.Reset)
    def on_list(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: ir.Statement,
    ) -> interp.StatementResult[EmptyLattice]:
        """Check the qubit list of a measurement or a reset."""
        check.items(stmt, stmt.args[0])
        return check.accept(frame, stmt)

    @interp.impl(qubit_stmts.IsZero)
    def is_zero(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: qubit_stmts.IsZero,
    ) -> interp.StatementResult[EmptyLattice]:
        """Refuse a negation of a bit array of unknown length."""
        check.negated(stmt, stmt.measurements)
        return check.accept(frame, stmt)

    @interp.impl(qubit_stmts.IsOne)
    def is_one(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: qubit_stmts.IsOne,
    ) -> interp.StatementResult[EmptyLattice]:
        """Accept the bits as they are."""
        return check.accept(frame, stmt)


@func.dialect.register(key=KEY)
class _Func(interp.MethodTable):
    """A method table that refuses calls and returns that jeff cannot express."""

    @interp.impl(func.Invoke)
    def invoke(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: func.Invoke,
    ) -> interp.StatementResult[EmptyLattice]:
        """Check a call from the caller's side.

        A library kernel call is checked as its statements. A user kernel gets its
        own validation run.
        """
        if is_library(stmt.callee):
            self.library(check, stmt)
            return check.accept(frame, stmt)
        if not isinstance(stmt.callee.code, func.Function):
            check.refuse(stmt, "a call of a function defined inside a kernel")
            return check.accept(frame, stmt)
        for arg in stmt.inputs:
            match check.refs[arg]:
                case Whole() | Register() | Slot():
                    pass
                case Unknown(reason):
                    check.refuse(stmt, reason)
                case Members():
                    check.refuse(stmt, "a literal list passed to a call")
                case _ if _listed(arg.type):
                    check.refuse(stmt, f"a value of type {arg.type} passed to a call")
        qubits = [check.refs[arg] for arg in stmt.inputs]
        check.distinct(stmt, [ref for ref in qubits if not isinstance(ref, Untracked)])
        kinds = declared_outputs(stmt.result.type)
        for ref in positions(check.refs[stmt.result], len(kinds)):
            if isinstance(ref, Unknown):
                check.refuse(stmt, ref.reason)
        return check.accept(frame, stmt)

    def library(self, check: SquinToJeffAnalysis, stmt: func.Invoke) -> None:
        """Check the qubit operands of a library kernel call."""
        if (form := GATE_KERNELS.get(stmt.callee)) is not None:
            check.gate(stmt, stmt.inputs[form.angles :])
        match QUBIT_KERNELS.get(stmt.callee):
            case qubit_stmts.Reset | qubit_stmts.Measure:
                check.items(stmt, stmt.inputs[0])
            case qubit_stmts.IsZero:
                check.negated(stmt, stmt.inputs[0])

    @interp.impl(func.Call)
    def call(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: func.Call,
    ) -> interp.StatementResult[EmptyLattice]:
        """Refuse a call of a runtime value."""
        check.refuse(stmt, "a call of a runtime value")
        return check.accept(frame, stmt)

    @interp.impl(func.Return)
    def return_(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: func.Return,
    ) -> interp.ReturnValue[EmptyLattice]:
        """Check that each returned value is a wire, a register or a scalar."""
        owner = stmt.value.owner
        if isinstance(owner, py.Constant):
            return interp.ReturnValue(check.lattice.top())
        kinds = declared_outputs(stmt.value.type)
        refs = positions(check.refs[stmt.value], len(kinds))
        for ref, kind in zip(refs, kinds, strict=True):
            match ref:
                case Whole() | Register():
                    pass
                case Slot():
                    check.refuse(
                        stmt, "a function that returns one qubit of a register"
                    )
                case Members():
                    check.refuse(stmt, "a function that returns a list of qubits")
                case Unknown(reason):
                    check.refuse(stmt, reason)
                case _ if _listed(kind):
                    check.refuse(
                        stmt, f"a function that returns a value of type {kind}"
                    )
        check.read(frame, stmt, stmt.args)
        return interp.ReturnValue(check.lattice.top())


@scf.dialect.register(key=KEY)
class _Scf(interp.MethodTable):
    """A method table that runs the regions of kirin control flow."""

    @interp.impl(scf.For)
    def for_(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: scf.For,
    ) -> interp.StatementResult[EmptyLattice]:
        """Check that the loop runs over a range, then run its body."""
        if loop_range(stmt.iterable) is None:
            check.refuse(stmt, "a loop over a value that is not a range")
        return check.regions(frame, stmt)

    @interp.impl(scf.IfElse)
    def if_else(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: scf.IfElse,
    ) -> interp.StatementResult[EmptyLattice]:
        """Run both branches."""
        return check.regions(frame, stmt)

    @interp.impl(scf.Yield)
    def yield_(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: scf.Yield,
    ) -> interp.YieldValue[EmptyLattice]:
        """End the region with the yielded values."""
        return interp.YieldValue(check.read(frame, stmt, stmt.values))


@math.dialect.register(key=KEY)
class _Math(interp.MethodTable):
    """A method table that refuses logarithms with a runtime base."""

    @interp.impl(math_stmts.log)
    def log(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: math_stmts.log,
    ) -> interp.StatementResult[EmptyLattice]:
        """Accept a logarithm with a constant base, which scales the natural one."""
        if not isinstance(stmt.base.owner, py.Constant):
            check.refuse(
                stmt, "a logarithm with a runtime base, which jeff cannot divide by"
            )
        return check.accept(frame, stmt)


@py.unary.dialect.register(key=KEY)
class _Unary(interp.MethodTable):
    """A method table that refuses unary operators that change a bool to an int."""

    @interp.impl(py.unary.USub)
    @interp.impl(py.unary.Invert)
    def on_bool(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: ir.Statement,
    ) -> interp.StatementResult[EmptyLattice]:
        """Refuse `-` or `~` on a bool, since Python gives an int there."""
        if stmt.args[0].type.is_subseteq(types.Bool):
            check.refuse(stmt, f"'{stmt.name}' on a bool, which gives an int in Python")
        return check.eval_fallback(frame, stmt)


@py.binop.dialect.register(key=KEY)
@py.cmp.dialect.register(key=KEY)
class _Arithmetic(interp.MethodTable):
    """A method table that refuses float arithmetic that jeff cannot express."""

    @interp.impl(py.binop.Add)
    @interp.impl(py.binop.Sub)
    @interp.impl(py.binop.Mult)
    @interp.impl(py.binop.Div)
    @interp.impl(py.binop.Mod)
    @interp.impl(py.binop.Pow)
    @interp.impl(py.binop.LShift)
    @interp.impl(py.binop.RShift)
    @interp.impl(py.binop.BitAnd)
    @interp.impl(py.binop.BitOr)
    @interp.impl(py.binop.BitXor)
    @interp.impl(py.binop.FloorDiv)
    @interp.impl(py.binop.MatMult)
    @interp.impl(py.cmp.Eq)
    @interp.impl(py.cmp.NotEq)
    @interp.impl(py.cmp.Lt)
    @interp.impl(py.cmp.Gt)
    @interp.impl(py.cmp.LtE)
    @interp.impl(py.cmp.GtE)
    @interp.impl(py.cmp.Is)
    @interp.impl(py.cmp.IsNot)
    @interp.impl(py.cmp.In)
    @interp.impl(py.cmp.NotIn)
    def floats(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: ir.Statement,
    ) -> interp.StatementResult[EmptyLattice]:
        """Refuse a float operation without a jeff form, or an int mixed with a float.

        Jeff cannot convert an integer to a float, except a constant, which the
        emitter writes as a float constant.
        """
        floats = [arg.type.is_subseteq(types.Float) for arg in stmt.args]
        if any(floats) and SWAPPED.get(type(stmt), type(stmt)) not in FLOAT_BINARY:
            check.refuse(stmt, f"jeff has no float form for '{stmt.name}'")
        if any(floats) and not all(floats):
            for arg in stmt.args:
                if not arg.type.is_subseteq(types.Float) and not isinstance(
                    arg.owner, py.Constant
                ):
                    check.refuse(
                        stmt, "an integer mixed with a float, which jeff cannot convert"
                    )
        return check.eval_fallback(frame, stmt)


@py.constant.dialect.register(key=KEY)
class _Constant(interp.MethodTable):
    """A method table that refuses constants that jeff cannot hold."""

    @interp.impl(py.Constant)
    def constant(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: py.Constant,
    ) -> interp.StatementResult[EmptyLattice]:
        """Accept a number, a bit and a range, and refuse any other constant."""
        match stmt.value.unwrap():
            case bool() | int() | float():
                pass
            case ilist.IList(data=range()):
                pass
            case ilist.IList(data=list(items)) if all(
                isinstance(item, (bool, int, float)) for item in items
            ):
                pass
            case tuple(items) if all(_number_or_list(item) for item in items):
                pass
            case _:
                check.refuse(stmt, f"a constant of type {stmt.result.type}")
        return check.accept(frame, stmt)


@py.indexing.dialect.register(key=KEY)
class _Indexing(interp.MethodTable):
    """A method table that refuses reads that jeff cannot express."""

    @interp.impl(py.indexing.GetItem)
    def getitem(
        self,
        check: SquinToJeffAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: py.indexing.GetItem,
    ) -> interp.StatementResult[EmptyLattice]:
        """Check a read of a register, a list or a tuple."""
        match check.refs[stmt.result]:
            case Unknown(reason):
                check.refuse(stmt, reason)
            case Slot(_, int(index)) if index < 0:
                check.refuse(stmt, "a negative index into a register of unknown length")
            case Whole() | Slot() | Members():
                pass
            case _ if stmt.obj.type.is_subseteq(types.Tuple) and (
                constant_int(stmt.index) is None
            ):
                check.refuse(stmt, "a tuple read at a runtime index")
        return check.accept(frame, stmt)


@dataclass
class SquinToJeffValidation(ValidationPass[ForwardFrame[EmptyLattice]]):
    """A validation pass that reports every construct of one squin kernel that jeff cannot express.

    The pass checks one kernel. `SquinToJeff` runs it on every kernel that a
    conversion reaches.
    """

    references: ForwardFrame[Ref] | None = field(default=None, init=False)
    """The frame of `QubitReferenceAnalysis` on the kernel, from the validation suite."""

    def name(self) -> str:
        """Return the pass name that refusals show."""
        return "SquinToJeff"

    def get_required_analyses(self) -> list[type]:
        """Return the analysis whose references the checks read."""
        return [QubitReferenceAnalysis]

    def set_analysis_cache(self, cache: dict[type, Any]) -> None:
        """Keep the frame of the reference analysis from the suite."""
        self.references = cache.get(QubitReferenceAnalysis)

    def run(
        self, method: ir.Method
    ) -> tuple[ForwardFrame[EmptyLattice], list[ir.ValidationError]]:
        """Check `method`, and run the reference analysis first if no suite did."""
        if self.references is None:
            self.references, _ = QubitReferenceAnalysis(method.dialects).run(method)
        analysis = SquinToJeffAnalysis(method.dialects, refs=self.references.entries)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
