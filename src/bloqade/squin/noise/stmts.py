import ast
from dataclasses import dataclass

from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

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


@statement
class NoiseChannel(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})


@statement
class SingleQubitNoiseChannel(NoiseChannel):
    # NOTE: we are not adding e.g. qubits here, since inheriting then will
    # change the order of the wrapper arguments
    pass


@statement
class TwoQubitNoiseChannel(NoiseChannel):
    pass


N = types.TypeVar("N", bound=types.Int)


@dataclass(frozen=True)
class TwoQubitPauliChannelLowering(lowering.FromPythonCall["TwoQubitPauliChannel"]):
    def lower(
        self,
        stmt: type["TwoQubitPauliChannel"],
        state: lowering.State[ast.AST],
        node: ast.Call,
    ) -> lowering.Result:
        arg_nodes = self._parse_call_args(node)

        probabilities = self._lower_probabilities(state, arg_nodes["probabilities"])
        controls = self._lower_qubits(state, arg_nodes["controls"])
        targets = self._lower_qubits(state, arg_nodes["targets"])
        return state.current_frame.push(stmt(probabilities, controls, targets))

    def _parse_call_args(self, node: ast.Call) -> dict[str, ast.AST]:
        arg_names = ("probabilities", "controls", "targets")
        if len(node.args) > len(arg_names):
            raise lowering.BuildError(
                "two_qubit_pauli_channel expects probabilities, controls, and targets"
            )

        arg_nodes = dict(zip(arg_names, node.args))
        for keyword in node.keywords:
            if keyword.arg not in arg_names:
                raise lowering.BuildError(f"Unexpected keyword argument {keyword.arg}")
            if keyword.arg in arg_nodes:
                raise lowering.BuildError(
                    f"Argument {keyword.arg} was provided more than once"
                )
            arg_nodes[keyword.arg] = keyword.value

        missing_args = set(arg_names) - set(arg_nodes)
        if missing_args:
            missing = ", ".join(sorted(missing_args))
            raise lowering.BuildError(f"Missing required argument(s): {missing}")

        return arg_nodes

    def _lower_probabilities(
        self, state: lowering.State[ast.AST], node: ast.AST
    ) -> ir.SSAValue:
        if not isinstance(node, ast.Dict):
            return state.lower(node).expect_one()

        probabilities: dict[str, ir.SSAValue] = {}
        for key, value in zip(node.keys, node.values):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                raise lowering.BuildError(
                    "two-qubit Pauli probability keys must be string literals"
                )
            if key.value not in PAULI_PRODUCT_ORDER:
                raise lowering.BuildError(
                    f"Invalid two-qubit Pauli product key: {key.value}"
                )
            probabilities[key.value] = state.lower(value).expect_one()

        values = tuple(
            probabilities.get(pauli_product, state.get_literal(0.0))
            for pauli_product in PAULI_PRODUCT_ORDER
        )
        return state.current_frame.push(
            ilist.New(values=values, elem_type=types.Float)
        ).result

    def _lower_qubits(
        self, state: lowering.State[ast.AST], node: ast.AST
    ) -> ir.SSAValue:
        qubits = state.lower(node).expect_one()
        if qubits.type.is_subseteq(ilist.IListType[QubitType, N]):
            return qubits

        if isinstance(node, ast.List):
            return qubits

        return state.current_frame.push(
            ilist.New(values=(qubits,), elem_type=QubitType)
        ).result


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


@statement(dialect=dialect)
class TwoQubitPauliChannel(TwoQubitNoiseChannel):
    """
    This will apply one of the randomly chosen Pauli products:

    {IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}

    but the choice is weighed with the given probability.

    NOTE: the given parameters are ordered as given in the list above!
    """

    traits = frozenset({TwoQubitPauliChannelLowering()})
    probabilities: ir.SSAValue = info.argument(
        ilist.IListType[types.Float, types.Literal(15)]
    )
    controls: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])
    targets: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])


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
