"""This module holds the loader that imports jeff programs as jeff dialect IR."""

from typing import cast
from pathlib import Path
from collections.abc import Sequence

from kirin import ir, types
from kirin.dialects import func
from kirin.validation import ValidationSuite

import jeff as jf
from bloqade.jeff import types as jeff_types
from bloqade.jeff.names import SCALARS
from bloqade.jeff.errors import JeffImportError
from bloqade.jeff.dialects import stmts, kernel as _kernel_group
from bloqade.jeff.signature import output_type
from bloqade.jeff.analysis.validation import LinearityValidation, StructureValidation


def _int_data(op: jf.JeffOp) -> int:
    """Return the integer that an operation carries as its instruction data."""
    data = op.instruction_data
    if not isinstance(data, int):
        raise JeffImportError(f"{op.kind}.{op.subkind} carries no integer")
    return int(data)


def _float_data(op: jf.JeffOp) -> float:
    """Return the number that an operation carries as its instruction data."""
    data = op.instruction_data
    if not isinstance(data, (int, float)):
        raise JeffImportError(f"{op.kind}.{op.subkind} carries no number")
    return float(data)


def _list_data(op: jf.JeffOp) -> list[int | float]:
    """Return the numbers that an operation carries as its instruction data."""
    data = op.instruction_data
    if isinstance(data, (str, bytes)):
        raise JeffImportError(f"{op.kind}.{op.subkind} carries no values")
    try:
        values = list(cast("Sequence[object]", data))
    except TypeError:
        raise JeffImportError(f"{op.kind}.{op.subkind} carries no values") from None
    numbers: list[int | float] = []
    for value in values:
        if not isinstance(value, (int, float)):
            raise JeffImportError(
                f"{op.kind}.{op.subkind} carries a value that is no number"
            )
        numbers.append(value)
    return numbers


def _bitwidth(op: jf.JeffOp) -> int:
    """Return the bitwidth of the integer or integer array an operation produces."""
    kind = op.outputs[0].type
    if not isinstance(kind, (jf.IntType, jf.IntArrayType)):
        raise JeffImportError(f"{op.kind}.{op.subkind} produces no integer")
    return kind.bitwidth


def _id(value: jf.JeffValue) -> int:
    """Return the id of a value.

    Raise `JeffImportError` if the value has no id.
    """
    if value.id is None:
        raise JeffImportError(
            "a value has no id. Refresh the module before you load it."
        )
    return value.id


def load_jeff(source: str | Path | jf.JeffModule) -> ir.Method:
    """Import a jeff module and return its entry function as a kirin method.

    The loader imports every function that the entry function reaches.
    The jeff validation passes then check the result.
    """
    if isinstance(source, (str, Path)):
        module = _read(Path(source))
    elif isinstance(source, jf.JeffModule):
        module = source
    else:
        raise TypeError(
            "load_jeff takes a path or a jeff module, and it got "
            f"{type(source).__name__}"
        )
    _check_version(module)
    try:
        entry = _Importer(module).function(module.entrypoint)
    except JeffImportError:
        raise
    except Exception as error:
        raise JeffImportError(f"malformed jeff module: {error}") from error
    passes = [StructureValidation, LinearityValidation]
    ValidationSuite(passes).validate(entry).raise_if_invalid()
    return entry


def _check_version(module: jf.JeffModule) -> None:
    """Check that the module uses the major and minor schema version of this reader.

    Raise `JeffImportError` if either number differs.
    """
    version = module.version
    major, minor = jf.schema.schemaVersionMajor, jf.schema.schemaVersionMinor
    if version is None or (version.major, version.minor) != (major, minor):
        raise JeffImportError(
            f"this reader does not support schema version {version}. "
            f"It reads version {major}.{minor}.x."
        )


def _read(path: Path) -> jf.JeffModule:
    """Read the jeff module that the file at `path` holds."""
    try:
        with open(path, "rb") as file:
            raw = jf.schema.Module.read(file, traversal_limit_in_words=1 << 62)
        return jf.JeffModule.from_encoding(raw)
    except OSError:
        raise
    except Exception as error:
        raise JeffImportError(f"'{path}' is not a jeff module: {error}") from error


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
    if isinstance(jeff_type, jf.QubitType):
        return jeff_types.WireType
    if isinstance(jeff_type, jf.QuregType):
        return jeff_types.qureg(jeff_type.length)
    if isinstance(jeff_type, jf.IntType):
        if jeff_type.bitwidth == 1:
            return types.Bool
        if jeff_type.bitwidth == 32:
            return types.Int
        raise JeffImportError(f"unsupported int bitwidth: {jeff_type.bitwidth}")
    if isinstance(jeff_type, jf.FloatType):
        if jeff_type.bitwidth == 64:
            return types.Float
        raise JeffImportError(f"unsupported float bitwidth: {jeff_type.bitwidth}")
    if isinstance(jeff_type, jf.IntArrayType):
        return jeff_types.IntArrayType
    if isinstance(jeff_type, jf.FloatArrayType):
        return jeff_types.FloatArrayType
    raise JeffImportError(f"unsupported value type: {jeff_type}")


class _Importer:
    """Import the functions of a jeff module as kirin methods."""

    def __init__(self, module: jf.JeffModule) -> None:
        """Start an importer for `module` with no imported methods."""
        self.module = module
        self.methods: dict[int, ir.Method] = {}

    def function(self, index: int) -> ir.Method:
        """Return the method for the function at `index`, and import it on first use."""
        if index in self.methods:
            return self.methods[index]
        function = self.module[index]
        if not isinstance(function, jf.FunctionDef):
            raise JeffImportError(f"function {index} is a declaration without a body")
        name = function.name

        block = ir.Block()
        block.args.append_from(types.Any, "self")
        values: dict[int, ir.SSAValue] = {}
        input_types: list[types.TypeAttribute] = []
        for source in function.body.sources:
            kirin_type = _kirin_type(source.type)
            values[_id(source)] = block.args.append_from(kirin_type, None)
            input_types.append(kirin_type)

        code = func.Function(
            sym_name=name,
            body=ir.Region(block),
            signature=func.Signature(inputs=tuple(input_types), output=types.Any),
        )
        method = ir.Method(dialects=_kernel_group, code=code, sym_name=name)
        self.methods[index] = method

        self._place_ops(function.body, block, values)
        targets = [values[_id(target)] for target in function.body.targets]
        block.stmts.append(stmts.Return(*targets))
        code.signature = func.Signature(
            inputs=tuple(input_types), output=output_type(targets)
        )
        return method

    def _place_ops(
        self, region: jf.JeffRegion, block: ir.Block, values: dict[int, ir.SSAValue]
    ) -> None:
        """Append the statements for the operations of `region` to `block` in order.

        Raise `JeffImportError` if an operation uses a value before its definition.
        """
        for op in region.operations:
            for value in op.inputs:
                if _id(value) not in values:
                    raise JeffImportError(
                        f"value {_id(value)} is used before it is defined"
                    )
            self._op(op, block, values)

    def _region_block(
        self, jeff_region: jf.JeffRegion, values: dict[int, ir.SSAValue]
    ) -> ir.Block:
        """Return a block that runs `jeff_region` and yields the region targets."""
        block = ir.Block()
        for source in jeff_region.sources:
            values[_id(source)] = block.args.append_from(_kirin_type(source.type), None)
        self._place_ops(jeff_region, block, values)
        block.stmts.append(
            stmts.Yield(*[values[_id(target)] for target in jeff_region.targets])
        )
        return block

    def _op(
        self, op: jf.JeffOp, block: ir.Block, values: dict[int, ir.SSAValue]
    ) -> None:
        """Append the statement for `op` to `block` and record its outputs."""
        kind = op.kind
        inputs = [values[_id(value)] for value in op.inputs]

        if kind == "func":
            # TODO: Read the call index from `op.instruction_data` after jeff-py
            # fixes unitaryfoundation/jeff#111. Until that fix, the loader reads
            # the call index from the raw capnp struct.
            index = int(op._raw_data.instruction.func.funcCall)
            callee = self.function(index)
            result_types = [_kirin_type(value.type) for value in op.outputs]
            statement = stmts.Call(callee, tuple(inputs), result_types)
        elif kind == "qubit" and op.subkind == "gate":
            statement = self._gate(op, inputs)
        elif kind == "qubit":
            cls = _QUBIT.get(op.subkind)
            if cls is None:
                raise JeffImportError(f"unsupported qubit op: {op.subkind}")
            statement = cls(*inputs)
        elif kind == "qureg":
            if op.subkind == "create":
                statement = stmts.RegCreate(tuple(inputs))
            else:
                cls = _QUREG.get(op.subkind)
                if cls is None:
                    raise JeffImportError(f"unsupported qureg op: {op.subkind}")
                statement = cls(*inputs)
        elif kind in ("int", "float") and op.subkind.startswith("const"):
            bitwidth = int(op.subkind.removeprefix("const"))
            if kind == "int":
                statement = stmts.ConstInt(
                    value=_signed(_int_data(op), bitwidth), bitwidth=bitwidth
                )
            else:
                statement = stmts.ConstFloat(value=_float_data(op), bitwidth=bitwidth)
        elif kind in ("int", "float"):
            cls = SCALARS.get((kind, op.subkind))
            if cls is None:
                raise JeffImportError(f"unsupported {kind} op: {op.subkind}")
            statement = cls(*inputs)
        elif kind in ("intArray", "floatArray"):
            statement = self._array(op, inputs)
        elif kind == "scf":
            statement = self._scf(op, inputs, values)
        else:
            raise JeffImportError(f"unsupported operation kind: {kind}")

        block.stmts.append(statement)
        if len(op.outputs) != len(statement.results):
            raise JeffImportError(
                f"{kind}.{op.subkind} has {len(op.outputs)} outputs. "
                f"The statement expects {len(statement.results)}."
            )
        for value, result in zip(op.outputs, statement.results, strict=True):
            kirin_type = _kirin_type(value.type)
            if (
                isinstance(value.type, jf.QuregType)
                and value.type.length is None
                and jeff_types.is_subtype(result.type, jeff_types.QuregType)
            ):
                # The statement type keeps a register length that the file omits.
                kirin_type = result.type
            result.type = kirin_type
            if _id(value) in values:
                raise JeffImportError(f"value {_id(value)} is produced twice")
            values[_id(value)] = result

    def _gate(self, op: jf.JeffOp, inputs: list[ir.SSAValue]) -> ir.Statement:
        """Return the gate statement for a jeff gate operation."""
        data = op.instruction_data
        if isinstance(data, (jf.WellKnowGate, jf.CustomGate)):
            name = data.kind if isinstance(data, jf.WellKnowGate) else data.name
            num_qubits, num_controls = data.num_qubits, data.num_controls
            return stmts.Gate(
                tuple(inputs[:num_qubits]),
                tuple(inputs[num_qubits : num_qubits + num_controls]),
                tuple(inputs[num_qubits + num_controls :]),
                gate_name=str(name),
                adjoint=bool(data.adjoint),
                power=int(data.power),
            )
        if isinstance(data, jf.PPRGate):
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
        raise JeffImportError(f"unsupported gate form: {type(data).__name__}")

    def _array(self, op: jf.JeffOp, inputs: list[ir.SSAValue]) -> ir.Statement:
        """Return the array statement for a jeff array operation."""
        kind, subkind = op.kind, op.subkind
        is_int = kind == "intArray"
        if subkind.startswith("const"):
            bitwidth = int(subkind.removeprefix("const"))
            data = _list_data(op)
            if is_int:
                return stmts.IntArrayConst(
                    values=tuple(_signed(int(x), bitwidth) for x in data),
                    bitwidth=bitwidth,
                )
            return stmts.FloatArrayConst(values=tuple(float(x) for x in data))
        if subkind == "zero":
            if is_int:
                return stmts.IntArrayZero(inputs[0], bitwidth=_int_data(op))
            return stmts.FloatArrayZero(inputs[0])
        if subkind == "getIndex":
            if is_int:
                bitwidth = _bitwidth(op)
                return stmts.IntArrayGet(inputs[0], inputs[1], bitwidth=bitwidth)
            return stmts.FloatArrayGet(inputs[0], inputs[1])
        if subkind == "setIndex":
            cls = stmts.IntArraySet if is_int else stmts.FloatArraySet
            return cls(inputs[0], inputs[1], inputs[2])
        if subkind == "length":
            cls = stmts.IntArrayLen if is_int else stmts.FloatArrayLen
            return cls(inputs[0])
        if subkind == "create":
            if is_int:
                bitwidth = _bitwidth(op)
                return stmts.IntArrayCreate(tuple(inputs), bitwidth=bitwidth)
            return stmts.FloatArrayCreate(tuple(inputs))
        raise JeffImportError(f"unsupported {kind} op: {subkind}")

    def _scf(
        self, op: jf.JeffOp, inputs: list[ir.SSAValue], values: dict[int, ir.SSAValue]
    ) -> ir.Statement:
        """Return the loop or switch statement for a jeff `scf` operation."""
        data = op.instruction_data
        if isinstance(data, jf.ForSCF):
            body = ir.Region(self._region_block(data.body, values))
            return stmts.For(inputs[0], inputs[1], inputs[2], tuple(inputs[3:]), body)
        if isinstance(data, jf.SwitchSCF):
            if data.default is None:
                raise JeffImportError("a switch has no default region")
            branches = [
                ir.Region(self._region_block(branch, values))
                for branch in data.branches
            ]
            default = ir.Region(self._region_block(data.default, values))
            return stmts.Switch(inputs[0], tuple(inputs[1:]), branches, default)
        if isinstance(data, jf.WhileSCF):
            before = ir.Region(self._region_block(data.before, values))
            after = ir.Region(self._region_block(data.after, values))
            return stmts.While(tuple(inputs), before, after)
        raise JeffImportError(f"unsupported scf form: {type(data).__name__}")
