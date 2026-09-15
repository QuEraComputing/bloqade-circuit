"""This module holds the kirin lowering from a jeff module to jeff dialect IR."""

from typing import cast
from dataclasses import field, dataclass
from collections.abc import Sequence

from kirin import ir, types, lowering
from kirin.dialects import func

import jeff as jf
from bloqade.jeff import types as jeff_types
from bloqade.jeff.names import SCALARS
from bloqade.jeff.errors import JeffImportError
from bloqade.jeff.dialects import stmts

Node = jf.FunctionDef | jf.JeffOp
"""A node of the jeff syntax tree that the lowering visits."""


_QUBIT = {
    "alloc": stmts.Alloc,
    "free": stmts.Free,
    "freeZero": stmts.FreeZero,
    "measure": stmts.Measure,
    "measureNd": stmts.MeasureNd,
    "reset": stmts.Reset,
}

_QUREG = {
    "alloc": stmts.RegAlloc,
    "free": stmts.RegFree,
    "freeZero": stmts.RegFreeZero,
    "extractIndex": stmts.Extract,
    "insertIndex": stmts.Insert,
    "extractSlice": stmts.ExtractSlice,
    "insertSlice": stmts.InsertSlice,
    "split": stmts.RegSplit,
    "join": stmts.RegJoin,
    "length": stmts.RegLength,
}


def _signed(pattern: int, bitwidth: int) -> int:
    """Return the signed integer that a stored bit pattern of `bitwidth` bits encodes.

    A 1-bit pattern keeps its value 0 or 1.
    """
    if bitwidth > 1 and pattern >= 1 << (bitwidth - 1):
        return pattern - (1 << bitwidth)
    return pattern


def _kirin_type(jeff_type: jf.JeffType) -> types.TypeAttribute:
    """Return the kirin type for a jeff value type."""
    match jeff_type:
        case jf.QubitType():
            return jeff_types.WireType
        case jf.QuregType(length=length):
            return jeff_types.qureg(length)
        case jf.IntType(bitwidth=1):
            return types.Bool
        case jf.IntType(bitwidth=32):
            return types.Int
        case jf.FloatType(bitwidth=64):
            return types.Float
        case jf.IntArrayType():
            return jeff_types.IntArrayType
        case jf.FloatArrayType():
            return jeff_types.FloatArrayType
    raise JeffImportError(f"unsupported value type: {jeff_type}")


@dataclass
class JeffLowering(lowering.LoweringABC[Node]):
    """A lowering from the functions of one jeff module to jeff dialect IR.

    Each jeff value is a definition of the lowering frame under the name of its id.
    """

    module: jf.JeffModule = field(kw_only=True)
    """The jeff module that holds the functions."""

    methods: dict[int, ir.Method] = field(default_factory=dict, init=False)
    """The method of each function that the lowering has started, by function index."""

    def run(
        self,
        stmt: Node,
        *,
        source: str | None = None,
        globals: dict[str, object] | None = None,
        file: str | None = None,
        lineno_offset: int = 0,
        col_offset: int = 0,
        compactify: bool = True,
    ) -> ir.Region:
        """Lower the function definition `stmt` and return its body region."""
        if not isinstance(stmt, jf.FunctionDef):
            raise JeffImportError("the lowering starts at a function definition")
        state = lowering.State(
            self, file=file, lineno_offset=lineno_offset, col_offset=col_offset
        )
        return self.function(state, stmt).callable_region

    def method(self, index: int) -> ir.Method:
        """Return the method of the function at `index`, and lower it on first use."""
        if index not in self.methods:
            function = self.module[index]
            if not isinstance(function, jf.FunctionDef):
                raise JeffImportError(
                    f"function {index} is a declaration without a body"
                )
            self.function(lowering.State(self), function, index)
        return self.methods[index]

    def function(
        self,
        state: lowering.State[Node],
        function: jf.FunctionDef,
        index: int | None = None,
    ) -> ir.Method:
        """Lower `function` to a method, and record it in `methods` under `index`.

        The lowering records the method before it lowers the body, so that a
        recursive call finds the method.
        """
        inputs = tuple(_kirin_type(value.type) for value in function.body.sources)
        outputs = [_kirin_type(value.type) for value in function.body.targets]
        if not outputs:
            output = types.NoneType
        elif len(outputs) == 1:
            output = outputs[0]
        else:
            output = types.Generic(tuple, *outputs)
        block = ir.Block()
        block.args.append_from(
            types.MethodType[list(inputs), output], f"{function.name}_self"
        )
        with state.frame(
            function.body.operations, entr_block=block, finalize_next=False
        ) as frame:
            for value, kind in zip(function.body.sources, inputs, strict=True):
                self.define(frame, value, block.args.append_from(kind))
            code = func.Function(
                sym_name=function.name,
                body=frame.curr_region,
                signature=func.Signature(inputs=inputs, output=output),
            )
            method = ir.Method(self.dialects, code, sym_name=function.name)
            if index is not None:
                self.methods[index] = method
            frame.exhaust()
            frame.push(stmts.Return(*self.read(frame, function.body.targets)))
        return method

    def define(
        self, frame: lowering.Frame[Node], value: jf.JeffValue, ssa: ir.SSAValue
    ) -> None:
        """Define the jeff value `value` as `ssa` in `frame`."""
        name = str(value.id)
        if frame.get_local(name) is not None:
            raise JeffImportError(f"value {name} is produced twice")
        frame.defs[name] = ssa

    def read(
        self, frame: lowering.Frame[Node], values: Sequence[jf.JeffValue]
    ) -> list[ir.SSAValue]:
        """Return the SSA value of each jeff value in `values`."""
        found: list[ir.SSAValue] = []
        for value in values:
            ssa = frame.get_local(str(value.id))
            if ssa is None:
                raise JeffImportError(f"value {value.id} is used before it is defined")
            found.append(ssa)
        return found

    def region(self, state: lowering.State[Node], region: jf.JeffRegion) -> ir.Region:
        """Lower a jeff region of a control-flow operation to a region that yields."""
        block = ir.Block()
        with state.frame(
            region.operations, entr_block=block, finalize_next=False
        ) as frame:
            for value in region.sources:
                self.define(
                    frame, value, block.args.append_from(_kirin_type(value.type))
                )
            frame.exhaust()
            frame.push(stmts.Yield(*self.read(frame, region.targets)))
        return frame.curr_region

    def lower_literal(self, state: lowering.State[Node], value: object) -> ir.SSAValue:
        """Raise an error, because a jeff constant is an operation of its own."""
        raise JeffImportError("a jeff module holds no literal values")

    def lower_global(
        self, state: lowering.State[Node], node: Node
    ) -> lowering.LoweringABC.Result:
        """Return the method that the jeff call operation `node` calls."""
        if not isinstance(node, jf.JeffOp) or node.kind != "func":
            raise JeffImportError("only a call operation refers to a function")
        # TODO: Read the call index from `node.instruction_data` after jeff-py
        # fixes unitaryfoundation/jeff#111. Until that fix, the lowering reads
        # the call index from the raw capnp struct.
        index = int(node._raw_data.instruction.func.funcCall)
        return lowering.LoweringABC.Result(self.method(index))

    def visit(self, state: lowering.State[Node], node: Node) -> lowering.Result:
        """Lower the jeff operation `node` and define its outputs."""
        if not isinstance(node, jf.JeffOp):
            raise JeffImportError("a function definition is no operation")
        frame = state.current_frame
        inputs = self.read(frame, node.inputs)
        match node.kind:
            case "func":
                statement = self.call(state, node, inputs)
            case "qubit":
                statement = self.qubit(node, inputs)
            case "qureg":
                statement = self.register(node, inputs)
            case "int" | "float":
                statement = self.scalar(node, inputs)
            case "intArray" | "floatArray":
                statement = self.array(node, inputs)
            case "scf":
                statement = self.control_flow(state, node, inputs)
            case _:
                raise JeffImportError(f"unsupported operation kind: {node.kind}")
        frame.push(statement)
        if len(node.outputs) != len(statement.results):
            raise JeffImportError(
                f"{node.kind}.{node.subkind} has {len(node.outputs)} outputs. "
                f"The statement expects {len(statement.results)}."
            )
        for value, result in zip(node.outputs, statement.results, strict=True):
            kirin_type = _kirin_type(value.type)
            if (
                isinstance(value.type, jf.QuregType)
                and value.type.length is None
                and jeff_types.is_subtype(result.type, jeff_types.QuregType)
            ):
                # The statement type keeps a register length that the file omits.
                kirin_type = result.type
            result.type = kirin_type
            self.define(frame, value, result)
        return tuple(statement.results)

    def call(
        self, state: lowering.State[Node], op: jf.JeffOp, inputs: list[ir.SSAValue]
    ) -> ir.Statement:
        """Return the call statement for a jeff call operation."""
        callee = state.get_global(op).expect(ir.Method)
        result_types = [_kirin_type(value.type) for value in op.outputs]
        return stmts.Call(callee, tuple(inputs), result_types)

    def qubit(self, op: jf.JeffOp, inputs: list[ir.SSAValue]) -> ir.Statement:
        """Return the statement for a jeff qubit operation."""
        if op.subkind != "gate":
            cls = _QUBIT.get(op.subkind)
            if cls is None:
                raise JeffImportError(f"unsupported qubit op: {op.subkind}")
            return cls(*inputs)
        match op.instruction_data:
            case (jf.WellKnowGate(kind=name) | jf.CustomGate(name=name)) as data:
                num_qubits, num_controls = data.num_qubits, data.num_controls
                return stmts.Gate(
                    tuple(inputs[:num_qubits]),
                    tuple(inputs[num_qubits : num_qubits + num_controls]),
                    tuple(inputs[num_qubits + num_controls :]),
                    gate_name=str(name),
                    adjoint=bool(data.adjoint),
                    power=int(data.power),
                )
            case jf.PPRGate() as data:
                pauli = tuple(str(p) for p in data.pauli_string)
                num_targets = len(pauli)
                num_controls = data.num_controls
                return stmts.Ppr(
                    tuple(inputs[:num_targets]),
                    tuple(inputs[num_targets : num_targets + num_controls]),
                    inputs[-1],
                    pauli_string=pauli,
                    adjoint=bool(data.adjoint),
                    power=int(data.power),
                )
            case data:
                raise JeffImportError(f"unsupported gate form: {type(data).__name__}")

    def register(self, op: jf.JeffOp, inputs: list[ir.SSAValue]) -> ir.Statement:
        """Return the statement for a jeff register operation."""
        if op.subkind == "create":
            return stmts.RegCreate(tuple(inputs))
        cls = _QUREG.get(op.subkind)
        if cls is None:
            raise JeffImportError(f"unsupported qureg op: {op.subkind}")
        return cls(*inputs)

    def scalar(self, op: jf.JeffOp, inputs: list[ir.SSAValue]) -> ir.Statement:
        """Return the statement for a jeff integer or float operation."""
        match op.kind, op.subkind:
            case "int", subkind if subkind.startswith("const"):
                bitwidth = int(subkind.removeprefix("const"))
                value = _signed(int(cast(int, op.instruction_data)), bitwidth)
                return stmts.ConstInt(value=value, bitwidth=bitwidth)
            case "float", subkind if subkind.startswith("const"):
                bitwidth = int(subkind.removeprefix("const"))
                value = float(cast(float, op.instruction_data))
                return stmts.ConstFloat(value=value, bitwidth=bitwidth)
            case key if key in SCALARS:
                return SCALARS[key](*inputs)
        raise JeffImportError(f"unsupported {op.kind} op: {op.subkind}")

    def array(self, op: jf.JeffOp, inputs: list[ir.SSAValue]) -> ir.Statement:
        """Return the array statement for a jeff array operation."""
        match op.kind, op.subkind:
            case "intArray", "zero":
                return stmts.IntArrayZero(
                    inputs[0], bitwidth=cast(int, op.instruction_data)
                )
            case "floatArray", "zero":
                return stmts.FloatArrayZero(inputs[0])
            case "intArray", "getIndex":
                bitwidth = cast(jf.IntType, op.outputs[0].type).bitwidth
                return stmts.IntArrayGet(inputs[0], inputs[1], bitwidth=bitwidth)
            case "floatArray", "getIndex":
                return stmts.FloatArrayGet(inputs[0], inputs[1])
            case "intArray", "setIndex":
                return stmts.IntArraySet(inputs[0], inputs[1], inputs[2])
            case "floatArray", "setIndex":
                return stmts.FloatArraySet(inputs[0], inputs[1], inputs[2])
            case "intArray", "length":
                return stmts.IntArrayLen(inputs[0])
            case "floatArray", "length":
                return stmts.FloatArrayLen(inputs[0])
            case "intArray", "create":
                bitwidth = cast(jf.IntType, op.outputs[0].type).bitwidth
                return stmts.IntArrayCreate(tuple(inputs), bitwidth=bitwidth)
            case "floatArray", "create":
                return stmts.FloatArrayCreate(tuple(inputs))
            case "intArray", subkind if subkind.startswith("const"):
                bitwidth = int(subkind.removeprefix("const"))
                data = cast("Sequence[int]", op.instruction_data)
                return stmts.IntArrayConst(
                    values=tuple(_signed(int(x), bitwidth) for x in data),
                    bitwidth=bitwidth,
                )
            case "floatArray", subkind if subkind.startswith("const"):
                data = cast("Sequence[float]", op.instruction_data)
                return stmts.FloatArrayConst(values=tuple(float(x) for x in data))
        raise JeffImportError(f"unsupported {op.kind} op: {op.subkind}")

    def control_flow(
        self, state: lowering.State[Node], op: jf.JeffOp, inputs: list[ir.SSAValue]
    ) -> ir.Statement:
        """Return the loop or switch statement for a jeff `scf` operation."""
        match op.instruction_data:
            case jf.ForSCF(body=body):
                start, stop, step, *state_values = inputs
                return stmts.For(
                    start, stop, step, tuple(state_values), self.region(state, body)
                )
            case jf.SwitchSCF(branches=branches, default=default):
                if default is None:
                    raise JeffImportError("a switch has no default region")
                return stmts.Switch(
                    inputs[0],
                    tuple(inputs[1:]),
                    [self.region(state, branch) for branch in branches],
                    self.region(state, default),
                )
            case jf.WhileSCF(before=before, after=after):
                return stmts.While(
                    tuple(inputs), self.region(state, before), self.region(state, after)
                )
            case data:
                raise JeffImportError(f"unsupported scf form: {type(data).__name__}")
