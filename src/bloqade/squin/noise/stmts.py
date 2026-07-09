import ast
from dataclasses import dataclass
from collections.abc import Sequence

from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import py, func, ilist
from kirin.lowering import BuildError

from bloqade.types import QubitType

from ._dialect import dialect

PAULI_PRODUCT_ORDER = (
    "IX",
    "IY",
    "IZ",
    "XI",
    "XX",
    "XY",
    "XZ",
    "YI",
    "YX",
    "YY",
    "YZ",
    "ZI",
    "ZX",
    "ZY",
    "ZZ",
)

_PAULI_PRODUCT_INDEX = {pauli: index for index, pauli in enumerate(PAULI_PRODUCT_ORDER)}

_STATIC_SHORTHAND_ERROR = (
    "Pauli shorthand arguments to two_qubit_pauli_channel must be statically "
    "known. Use the full 15-probability signature for runtime values."
)


def _constant_sequence_from_ssa(value: ir.SSAValue) -> list:
    owner = value.owner
    if isinstance(owner, ilist.New):
        return [_constant_from_ssa(item) for item in owner.values]

    if isinstance(owner, py.constant.Constant):
        data = owner.value.unwrap()
        if isinstance(data, ilist.IList):
            return list(data)
        if isinstance(data, (list, tuple)):
            return list(data)

    raise BuildError(_STATIC_SHORTHAND_ERROR)


def _constant_from_ssa(value: ir.SSAValue):
    owner = value.owner
    if isinstance(owner, py.constant.Constant):
        return owner.value.unwrap()

    raise BuildError(_STATIC_SHORTHAND_ERROR)


def _constant_sequence_from_ast(state: lowering.State, node: ast.AST) -> list:
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_constant_from_ast(state, item) for item in node.elts]

    if isinstance(node, ast.Name):
        local = state.current_frame.get_local(node.id)
        if local is not None:
            return _constant_sequence_from_ssa(local)

    global_value = state.get_global(node, no_raise=True)
    if global_value is not None:
        data = global_value.data
        if isinstance(data, ilist.IList):
            return list(data)
        if isinstance(data, (list, tuple)):
            return list(data)

    raise BuildError(_STATIC_SHORTHAND_ERROR)


def _constant_from_ast(state: lowering.State, node: ast.AST):
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        local = state.current_frame.get_local(node.id)
        if local is not None:
            return _constant_from_ssa(local)

    global_value = state.get_global(node, no_raise=True)
    if global_value is not None:
        return global_value.data

    raise BuildError(_STATIC_SHORTHAND_ERROR)


def _two_qubit_pauli_probabilities(
    paulis: Sequence[object], probabilities: Sequence[object]
) -> list[float]:
    if len(paulis) != len(probabilities):
        raise BuildError(
            "Pauli shorthand arguments to two_qubit_pauli_channel must have the "
            "same length"
        )

    full_probabilities = [0.0 for _ in PAULI_PRODUCT_ORDER]
    seen: set[str] = set()
    for pauli, probability in zip(paulis, probabilities):
        if not isinstance(pauli, str):
            raise BuildError(
                "Pauli labels passed to two_qubit_pauli_channel must be strings"
            )
        if pauli not in _PAULI_PRODUCT_INDEX:
            raise BuildError(f"Invalid two-qubit Pauli product {pauli!r}")
        if pauli in seen:
            raise BuildError(f"Duplicate two-qubit Pauli product {pauli!r}")
        if not isinstance(probability, (int, float)):
            raise BuildError(
                "Probabilities passed to two_qubit_pauli_channel must be numbers"
            )

        seen.add(pauli)
        full_probabilities[_PAULI_PRODUCT_INDEX[pauli]] = float(probability)

    return full_probabilities


_two_qubit_pauli_channel_broadcast_callee: ir.Method | None = None


def register_two_qubit_pauli_channel_broadcast_callee(callee: ir.Method) -> None:
    """Defines a global kernel that other kernels can invoke."""
    global _two_qubit_pauli_channel_broadcast_callee
    _two_qubit_pauli_channel_broadcast_callee = callee


@dataclass(frozen=True)
class FromPythonCallTwoQubitPauliChannelSimple(lowering.FromPythonCall):
    """
    Custom lowering class that converts either an input that takes in a list of probabilities or two lists, one of paulis and one of
    probabilities.
    """

    def lower(
        self, stmt: type[ir.Statement], state: lowering.State, node: ast.Call
    ) -> lowering.Result:
        """
        Custom lowering that allows for a list of probabilities or two lists (one of paulis and one of probabilities.)
        """
        keyword_names = {keyword.arg for keyword in node.keywords}
        shorthand = (
            len(node.args) == 4
            or "paulis" in keyword_names
            or (
                len(node.args) == 2
                and bool(keyword_names & {"control", "controls"})
                and bool(keyword_names & {"target", "targets"})
            )
        )

        if shorthand:
            (
                paulis_node,
                probabilities_node,
                controls_node,
                targets_node,
            ) = _extract_call_arguments(
                node,
                ("paulis", "probabilities", "controls", "targets"),
                {"control": "controls", "target": "targets"},
            )

            paulis = _constant_sequence_from_ast(state, paulis_node)
            shorthand_probabilities = _constant_sequence_from_ast(
                state, probabilities_node
            )
            probabilities = _lower_probabilities(
                state,
                _two_qubit_pauli_probabilities(paulis, shorthand_probabilities),
            )
            controls, broadcast_controls = _lower_qubit_argument(state, controls_node)
            targets, broadcast_targets = _lower_qubit_argument(state, targets_node)
        else:
            probabilities_node, controls_node, targets_node = _extract_call_arguments(
                node,
                ("probabilities", "controls", "targets"),
                {"control": "controls", "target": "targets"},
            )
            probabilities = state.lower(probabilities_node).expect_one()
            controls, broadcast_controls = _lower_qubit_argument(state, controls_node)
            targets, broadcast_targets = _lower_qubit_argument(state, targets_node)

        if broadcast_controls or broadcast_targets:
            if _two_qubit_pauli_channel_broadcast_callee is None:
                raise BuildError(
                    "broadcast two_qubit_pauli_channel lowering is not registered"
                )

            return state.current_frame.push(
                func.Invoke(
                    (probabilities, controls, targets),
                    callee=_two_qubit_pauli_channel_broadcast_callee,
                )
            )

        return state.current_frame.push(
            TwoQubitPauliChannel(probabilities, controls, targets)
        )


def _extract_call_arguments(
    node: ast.Call, names: tuple[str, ...], aliases: dict[str, str]
) -> tuple[ast.AST, ...]:
    if len(node.args) > len(names):
        raise BuildError(
            "two_qubit_pauli_channel expects either "
            "(probabilities, control, target) or "
            "(paulis, probabilities, control, target)"
        )

    values = dict(zip(names, node.args))
    for keyword in node.keywords:
        if keyword.arg is None:
            raise BuildError(
                "two_qubit_pauli_channel does not support unpacked keyword arguments"
            )

        name = aliases.get(keyword.arg, keyword.arg)
        if name not in names:
            raise BuildError(
                f"Unexpected keyword argument {keyword.arg!r} "
                "for two_qubit_pauli_channel"
            )
        if name in values:
            raise BuildError(
                f"Argument {keyword.arg!r} was passed more than once "
                "to two_qubit_pauli_channel"
            )
        values[name] = keyword.value

    missing = [name for name in names if name not in values]
    if missing:
        raise BuildError(f"Missing argument {missing[0]!r} for two_qubit_pauli_channel")

    return tuple(values[name] for name in names)


def _lower_qubit_argument(
    state: lowering.State, node: ast.AST
) -> tuple[ir.SSAValue, bool]:
    value = state.lower(node).expect_one()
    if value.type.is_subseteq(ilist.IListType[QubitType, types.Any]):
        return value, True

    if (
        value.type.is_subseteq(QubitType)
        or _is_scalar_index(node)
        or _is_scalar_index_value(value)
    ):
        qubits = state.current_frame.push(
            ilist.New(values=(value,), elem_type=QubitType)
        ).result
        return qubits, False

    return value, True


def _is_scalar_index(node: ast.AST) -> bool:
    return isinstance(node, ast.Subscript) and not isinstance(node.slice, ast.Slice)


def _is_scalar_index_value(value: ir.SSAValue) -> bool:
    owner = value.owner
    return isinstance(owner, py.indexing.GetItem) and owner.index.type.is_subseteq(
        types.Int
    )


def _lower_probabilities(state: lowering.State, probabilities: Sequence[float]):
    values = tuple(state.get_literal(probability) for probability in probabilities)
    return state.current_frame.push(
        ilist.New(values=values, elem_type=types.Float)
    ).result


@statement
class NoiseChannel(ir.Statement):
    """A generic NoiseChannel statement."""

    traits = frozenset({lowering.FromPythonCall()})


@statement
class SingleQubitNoiseChannel(NoiseChannel):
    """A generic single qubit noise channel statement."""

    # NOTE: we are not adding e.g. qubits here, since inheriting then will
    # change the order of the wrapper arguments
    pass


@statement
class TwoQubitNoiseChannel(NoiseChannel):
    """A generic two qubit noise channel statement."""

    pass


@statement(dialect=dialect)
class SingleQubitPauliChannel(SingleQubitNoiseChannel):
    """
    This will apply one of the randomly chosen Pauli operators according to the
    given probabilities (p_x, p_y, p_z).
    """

    px: ir.SSAValue = info.argument(types.Float)
    py: ir.SSAValue = info.argument(types.Float)
    pz: ir.SSAValue = info.argument(types.Float)
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])


N = types.TypeVar("N", bound=types.Int)


@statement(dialect=dialect)
class TwoQubitPauliChannel(TwoQubitNoiseChannel):
    """
    This will apply one of the randomly chosen Pauli products:

    {IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}

    but the choice is weighed with the given probability.

    NOTE: the given parameters are ordered as given in the list above!
    """

    probabilities: ir.SSAValue = info.argument(
        ilist.IListType[types.Float, types.Literal(15)]
    )
    controls: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])
    targets: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])


@statement(dialect=dialect)
class TwoQubitPauliChannelSimple(ir.Statement):
    """Custom statement that defines lowering that allows for different input shapes for a list of probabilities or two lists."""

    traits = frozenset({FromPythonCallTwoQubitPauliChannelSimple()})


@statement(dialect=dialect)
class Depolarize(SingleQubitNoiseChannel):
    """
    Apply depolarize error to single qubit.

    This randomly picks one of the three Pauli operators to apply. Each Pauli
    operator has the probability `p / 3` to be selected. No operator is applied
    with the probability `1 - p`.
    """

    p: ir.SSAValue = info.argument(types.Float)
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])


@statement(dialect=dialect)
class Depolarize2(TwoQubitNoiseChannel):
    """
    Apply correlated depolarize error to two qubits

    This will apply one of the randomly chosen Pauli products each with probability `p / 15`:

    `{IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}`
    """

    p: ir.SSAValue = info.argument(types.Float)
    controls: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])
    targets: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])


@statement(dialect=dialect)
class QubitLoss(SingleQubitNoiseChannel):
    """
    Apply an atom loss with channel.
    """

    # NOTE: qubit loss error (not supported by Stim)
    p: ir.SSAValue = info.argument(types.Float)
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])


@statement(dialect=dialect)
class CorrelatedQubitLoss(NoiseChannel):
    """
    Apply a correlated atom loss channel.
    """

    p: ir.SSAValue = info.argument(types.Float)
    qubits: ir.SSAValue = info.argument(
        ilist.IListType[ilist.IListType[QubitType, N], types.Any]
    )
