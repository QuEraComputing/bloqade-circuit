"""Replace Jeff quantum operations and calls with explicit squin wire operations."""

import math
from dataclasses import dataclass
from collections.abc import Mapping

from kirin import ir, types
from kirin.dialects import py, func, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.jeff.forms import JEFF_TO_WIRE
from bloqade.jeff.gates import Shape, canonical
from bloqade.jeff.types import (
    WireType as JeffWireType,
    QuregType,
    IntArrayType,
    FloatArrayType,
    is_subtype,
    qureg_length,
)
from bloqade.squin.gate import stmts as gates
from bloqade.squin.wire import stmts as wire
from bloqade.jeff.dialects import stmts
from bloqade.squin.wire.types import WireType, register_type
from bloqade.squin.rewrite.wire.tools import put, pack, unpack, replace
from bloqade.squin.rewrite.wire.sources import ENTRIES
from bloqade.squin.rewrite.wire.signature import packed_type
from bloqade.jeff.analysis.validation.to_squin.gates import (
    SINGLE,
    ROTATION,
    CONTROLLED,
    NON_HERMITIAN,
    gate_supported,
)


def wire_type(typ: types.TypeAttribute) -> types.TypeAttribute:
    """Translate quantum and array types while retaining classical scalar types."""
    if is_subtype(typ, JeffWireType):
        return WireType
    if is_subtype(typ, QuregType):
        return register_type(qureg_length(typ))
    if is_subtype(typ, IntArrayType):
        return ilist.IListType[types.Int, types.Any]
    if is_subtype(typ, FloatArrayType):
        return ilist.IListType[types.Float, types.Any]
    if isinstance(typ, types.Generic) and is_subtype(typ, types.Tuple):
        return types.Generic(tuple, *(wire_type(member) for member in typ.vars))
    return typ


@dataclass
class Quantum(RewriteRule):
    """Replace each Jeff quantum statement, call and return with its wire form."""

    methods: Mapping[ir.Method, ir.Method]

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Replace a quantum operation, call or function return."""
        if build := JEFF_TO_WIRE.get(type(node)):
            made = put(build(*node.args), node)
            replace(node, *made.results)
        elif isinstance(node, stmts.RegCreate):
            replace(node, put(wire.PackRegister(node.wires), node).result)
        elif isinstance(node, (stmts.Measure, stmts.MeasureNd)):
            self.measure(node)
        elif isinstance(node, stmts.Gate):
            return self.gate(node)
        elif isinstance(node, stmts.Call):
            self.call(node)
        elif isinstance(node, stmts.Return):
            self.returned(node)
        else:
            return RewriteResult()
        return RewriteResult(has_done_something=True)

    def measure(self, node: stmts.Measure | stmts.MeasureNd) -> None:
        """Replace a Jeff measurement with a wire measurement.

        `MeasureNd` keeps its qubit. `Measure` frees it after the measurement.
        """
        measured = put(wire.Measure(node.wire), node)
        if isinstance(node, stmts.MeasureNd):
            replace(node, *measured.results)
            return
        put(wire.Free(measured.results[0]), node)
        replace(node, measured.results[1])

    def call(self, node: stmts.Call) -> None:
        """Replace a Jeff call with a call of the wire copy of its callee.

        A wire method returns several outputs as one tuple, so each result reads its
        position of that tuple.
        """
        callee = self.methods[node.callee]
        made = put(func.Invoke(node.inputs, callee=callee), node)
        outputs = tuple(wire_type(value.type) for value in node.results)
        made.result.type = packed_type(outputs)
        if len(outputs) == 1:
            replace(node, made.result)
            return
        replace(node, *unpack(made.result, outputs, node))

    def returned(self, node: stmts.Return) -> None:
        """Replace a Jeff return with a return of None, one value or a tuple."""
        node.replace_by(func.Return(pack(node.values, node)))

    def gate(self, node: stmts.Gate) -> RewriteResult:
        """Apply each gate power and map output wires to their declared operand positions."""
        shape = canonical(node)
        if not gate_supported(shape):
            raise ValueError(f"Gate '{shape.name}' has no squin wire form.")
        current = {value: value for value in (*node.targets, *node.controls)}
        if (form := wire_form(shape, node)) is not None:
            source, angles, adjoint = form
            operands = (*shape.controls, *shape.targets)
            for _ in range(shape.power):
                wires = tuple(current[value] for value in operands)
                made = put(ENTRIES[source].scalar(wires, angles, adjoint), node)
                current.update(zip(operands, made.outputs, strict=True))
        replace(node, *(current[value] for value in (*node.targets, *node.controls)))
        return RewriteResult(has_done_something=True)


def turns(radians: ir.SSAValue, before: ir.Statement) -> ir.SSAValue:
    """Return the Jeff angle `radians` in turns, which squin gates take."""
    scale = put(py.Constant(1 / (2 * math.pi)), before).result
    return put(py.Mult(radians, scale), before).result


def negative(value: ir.SSAValue, before: ir.Statement) -> ir.SSAValue:
    """Return the negation of the angle `value`."""
    return put(py.USub(value), before).result


def wire_form(
    shape: Shape, before: ir.Statement
) -> tuple[type[ir.Statement], tuple[ir.SSAValue, ...], bool] | None:
    """Return the squin statement, its angles and its adjoint flag for one gate power.

    The result is None for the identity and for an uncontrolled global phase, which
    act as no gate.
    """
    name = shape.name
    if len(shape.controls) == 1:
        return CONTROLLED[name], (), False
    if len(shape.controls) == 2:
        return gates.CCZ, (), False
    if name == "u":
        theta, phi, lam = (turns(value, before) for value in shape.params)
        if shape.adjoint:
            # The adjoint of U3(theta, phi, lam) is U3(-theta, -lam, -phi).
            theta, phi, lam = (negative(v, before) for v in (theta, lam, phi))
        return gates.U3, (theta, phi, lam), False
    if name == "swap":
        return gates.Swap, (), False
    if name in SINGLE:
        return SINGLE[name], (), False
    if name in NON_HERMITIAN:
        return NON_HERMITIAN[name], (), shape.adjoint
    if name in ROTATION:
        angle = turns(shape.params[0], before)
        return (
            ROTATION[name],
            (negative(angle, before) if shape.adjoint else angle,),
            False,
        )
    return None
