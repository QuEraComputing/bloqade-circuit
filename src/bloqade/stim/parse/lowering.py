"""One-to-one lowering routine from stim circuit to a stim-dialect kirin kernel."""

import pathlib
from typing import TYPE_CHECKING, Any, Union
from dataclasses import field, dataclass

import kirin
from kirin import ir, lowering
from kirin.dialects import func

import bloqade.stim as kstim
from bloqade.stim.dialects import gate, noise, collapse, auxiliary

if TYPE_CHECKING:
    import stim


Node = Union["stim.Circuit", "stim.CircuitInstruction", "stim.GateTarget"]
LiteralType = Union[bool, int, float, str]


def loads(
    stim_str: str,
    *,
    kernel_name: str = "main",
    ignore_unknown_stim: bool = False,
    error_unknown_nonstim: bool = False,
    nonstim_noise_ops: dict[str, type[kirin.ir.Statement]] = {},
    dialects: ir.DialectGroup | None = None,
    globals: dict[str, Any] | None = None,
    file: str | None = None,
    lineno_offset: int = 0,
    col_offset: int = 0,
    compactify: bool = True,
) -> ir.Method[[], None]:
    """Loads a STIM string and returns the corresponding kernel object.

    Args:
        stim_str: The string representation of a STIM circuit to load.

    Keyword Args:
        kernel_name (str): The name of the kernel to load. Defaults to "main".
        ignore_unknown_stim (bool): If True, don't throw a build error on an
            unimplemented stim instruction.
        error_unknown_nonstim (bool): If True, throw a build error if an unknown tag is
            used on the `I_ERROR` instruction.
        nonstim_noise_ops (dict[str, kirin.ir.Statement]): Additional statements to
            represent non-standard stim operations.  The dictionary key should match the
            tag used to identify it in stim (stim format
            `I_ERROR[MY_NOISE](0.05) 0 1 2 3` or
            `I_ERROR[MY_CORRELATED_NOISE:2417696374](0.03) 1 3 5`).
        dialects (ir.DialectGroup | None): The dialects to use. Defaults to `stim.main`.
        globals (dict[str, Any] | None): The global variables to use. Defaults to None.
        file (str | None): The file name for error reporting. Defaults to None.
        lineno_offset (int): The line number offset for error reporting. Defaults to 0.
        col_offset (int): The column number offset for error reporting. Defaults to 0.
        compactify (bool): Whether to compactify the output. Defaults to True.

    Example:

    ```python
    from bloqade.stim.lowering import loads
    method = loads('''
        X 0 2 4
        DEPOLARIZE1(0.01) 0
        I_ERROR[CUSTOM_ERROR](0.02) 2 4
        M 0 2 4
        DETECTOR rec[-1] rec[-2]
    ''')
    ```
    """
    import stim  # Optional dependency required to lower stim circuits

    circ = stim.Circuit(stim_str)
    stim_lowering = Stim(
        kstim.main if dialects is None else dialects,
        ignore_unknown_stim=ignore_unknown_stim,
        error_unknown_nonstim=error_unknown_nonstim,
        nonstim_noise_ops=nonstim_noise_ops,
    )
    frame = stim_lowering.get_frame(
        circ,
        source=stim_str,
        file=file,
        globals=globals,
        lineno_offset=lineno_offset,
        col_offset=col_offset,
        compactify=compactify,
    )

    return_value = func.ConstantNone()  # No return value
    frame.push(return_value)
    return_node = frame.push(func.Return(value_or_stmt=return_value))

    body = frame.curr_region
    code = func.Function(
        sym_name=kernel_name,
        signature=func.Signature((), return_node.value.type),
        body=body,
    )
    return ir.Method(
        mod=None,
        py_func=None,
        sym_name=kernel_name,
        arg_names=[],
        dialects=kstim.dialects,
        code=code,
    )


def loadfile(file: str | pathlib.Path):
    with open(file) as f:
        return loads(f.read())


@dataclass
class Stim(lowering.LoweringABC[Node]):
    max_lines: int = field(default=3, kw_only=True)
    hint_indent: int = field(default=2, kw_only=True)
    hint_show_lineno: bool = field(default=True, kw_only=True)
    stacktrace: bool = field(default=True, kw_only=True)
    nonstim_noise_ops: dict[str, kirin.ir.Statement] = field(
        default_factory=dict, kw_only=True
    )
    ignore_unknown_stim: bool = field(default=False, kw_only=True)
    error_unknown_nonstim: bool = field(default=False, kw_only=True)

    def run(
        self,
        stmt: Node,
        *,
        source: str | None = None,
        globals: dict[str, Any] | None = None,
        file: str | None = None,
        lineno_offset: int = 0,
        col_offset: int = 0,
        compactify: bool = True,
    ) -> ir.Region:

        frame = self.get_frame(
            stmt,
            source=source,
            globals=globals,
            file=file,
            lineno_offset=lineno_offset,
            col_offset=col_offset,
        )

        return frame.curr_region

    def get_frame(
        self,
        stmt: Node,
        source: str | None = None,
        globals: dict[str, Any] | None = None,
        file: str | None = None,
        lineno_offset: int = 0,
        col_offset: int = 0,
        compactify: bool = True,
    ) -> lowering.Frame:
        state = lowering.State(
            self,
            file=file,
            lineno_offset=lineno_offset,
            col_offset=col_offset,
        )
        with state.frame(
            [stmt],
            globals=globals,
            finalize_next=False,
        ) as frame:
            self.visit(state, stmt)

            if compactify:
                from kirin.rewrite import Walk, CFGCompactify

                Walk(CFGCompactify()).rewrite(frame.curr_region)

            return frame

    def lower_literal(
        self, state: lowering.State[Node], value: LiteralType
    ) -> ir.SSAValue:
        match value:
            case bool():
                stmt = auxiliary.ConstBool(value=value)
            case int():
                stmt = auxiliary.ConstInt(value=value)
            case float():
                stmt = auxiliary.ConstFloat(value=value)
            case str():
                stmt = auxiliary.ConstStr(value=value)
            case _:
                raise lowering.BuildError(
                    f"Expected value of type float or int, got {type(value)}."
                )
        state.current_frame.push(stmt)
        return stmt.result

    def lower_global(
        self,
        state: lowering.State[Node],
        node: Node,
    ) -> lowering.LoweringABC.Result:
        raise lowering.BuildError("Global variables are not supported in stim")

    def visit(self, state: lowering.State[Node], node: Node) -> lowering.Result:
        import stim  # Optional dependency required to lower stim circuits

        match node:
            case stim.Circuit() as circ:
                for inst in circ:
                    state.lower(inst)
            case stim.CircuitInstruction() as inst:
                return self.visit_CircuitInstruction(state, node)
            case _:
                raise lowering.BuildError(
                    f"Unexpected stim node: {type(node)} ({node!r})"
                )

    def _get_qubit_ssa(self, state: lowering.State[Node], target: Node):
        assert target.is_qubit_target, "expect qubit target"
        return self.lower_literal(state, target.qubit_value)

    def _get_rec_ssa(self, state: lowering.State[Node], node: Node, target: Node):
        assert target.is_measurement_record_target, "expect measurement record target"
        lit = self.lower_literal(state, target.value)
        stmt = auxiliary.GetRecord(id=lit)
        state.current_frame.push(stmt)
        return stmt.result

    def _get_pauli_string_ssa(self, state: lowering.State[Node], ps_target: list[Node]):
        basis_ssa_list = []
        flipped_ssa_list = []
        tgts_ssa_list = []

        for targ in ps_target:
            if targ.is_x_target:
                basis_ssa = self.lower_literal(state, "x")
            elif targ.is_y_target:
                basis_ssa = self.lower_literal(state, "y")
            elif targ.is_z_target:
                basis_ssa = self.lower_literal(state, "z")

            flip_ssa = self.lower_literal(state, targ.is_inverted_result_target)
            targ_ssa = self.lower_literal(state, targ.qubit_value)

            basis_ssa_list.append(basis_ssa)
            flipped_ssa_list.append(flip_ssa)
            tgts_ssa_list.append(targ_ssa)

        stmt = auxiliary.NewPauliString(
            string=tuple(basis_ssa_list),
            flipped=tuple(flipped_ssa_list),
            targets=tuple(tgts_ssa_list),
        )
        state.current_frame.push(stmt)
        return stmt.result

    def _get_multiple_qubit_or_rec_ssa(
        self, state: lowering.State[Node], node: Node, targets: list[Node]
    ):
        return tuple(
            (
                self._get_qubit_ssa(state, targ)
                if targ.is_qubit_target
                else self._get_rec_ssa(state, node, targ)
            )
            for targ in targets
        )

    def _get_pauli_string_targets_ssa(
        self, state: lowering.State[Node], node: Node, targets: list[Node]
    ):
        ps_list = []
        tmp = []
        prev_combine = True
        for targ in targets:
            if prev_combine is False and targ.is_combiner is False:
                ps_list.append(tmp)
                tmp = [targ]
            else:
                if not targ.is_combiner:
                    tmp.append(targ)
                prev_combine = not prev_combine

        ps_list.append(tmp)

        return tuple(self._get_pauli_string_ssa(state, ps) for ps in ps_list)

    def _get_float_args_ssa(
        self, state: lowering.State[Node], gate_args: list[LiteralType]
    ):
        return tuple(self.lower_literal(state, val) for val in gate_args)

    def _get_optional_float_arg_ssa(
        self, state: lowering.State[Node], gate_args: list[LiteralType]
    ):
        val = float(gate_args[0]) if len(gate_args) >= 1 else 0.0
        return self.lower_literal(state, val)

    def _get_optional_int_arg_ssa(
        self, state: lowering.State[Node], gate_args: list[LiteralType]
    ):
        val = int(gate_args[0]) if len(gate_args) >= 1 else 0
        return self.lower_literal(state, val)

    # Stim gates defined here: https://github.com/quantumlib/Stim/blob/main/doc/gates.md
    # collapse-------------------------:
    def _visit_reset(
        self, state: lowering.State[Node], name: str, node
    ) -> ir.Statement:
        return getattr(collapse, name)(
            targets=self._get_multiple_qubit_or_rec_ssa(
                state, node, node.targets_copy()
            )
        )

    def visit_RZ(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_reset(state, "RZ", node)

    def visit_RX(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_reset(state, "RX", node)

    def visit_RY(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_reset(state, "RY", node)

    def _visit_measure(
        self, state: lowering.State[Node], name: str, node
    ) -> ir.Statement:
        return getattr(collapse, name)(
            p=self._get_optional_float_arg_ssa(state, node.gate_args_copy()),
            targets=self._get_multiple_qubit_or_rec_ssa(
                state, node, node.targets_copy()
            ),
        )

    def visit_MX(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_measure(state, "MX", node)

    def visit_MY(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_measure(state, "MY", node)

    def visit_MZ(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_measure(state, "MZ", node)

    def visit_MXX(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_measure(state, "MXX", node)

    def visit_MYY(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_measure(state, "MYY", node)

    def visit_MZZ(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_measure(state, "MZZ", node)

    def visit_MPP(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return collapse.PPMeasurement(
            p=self._get_optional_float_arg_ssa(state, node.gate_args_copy()),
            targets=self._get_pauli_string_targets_ssa(
                state, node, node.targets_copy()
            ),
        )

    # aux.annotate-------------------------:
    def visit_TICK(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return auxiliary.Tick()

    def visit_DETECTOR(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return auxiliary.Detector(
            coord=self._get_float_args_ssa(state, node.gate_args_copy()),
            targets=self._get_multiple_qubit_or_rec_ssa(
                state, node, node.targets_copy()
            ),
        )

    def visit_OBSERVABLE_INCLUDE(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return auxiliary.ObservableInclude(
            idx=self._get_optional_int_arg_ssa(state, node.gate_args_copy()),
            targets=self._get_multiple_qubit_or_rec_ssa(
                state, node, node.targets_copy()
            ),
        )

    def visit_QUBIT_COORDS(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return auxiliary.QubitCoordinates(
            coord=self._get_float_args_ssa(state, node.gate_args_copy()),
            target=self._get_multiple_qubit_or_rec_ssa(
                state, node, node.targets_copy()
            )[0],
        )

    # gate: Clifford-------------------------:
    # NOTE, we don't need SQRT_Z and SQRT_Z_DAG because stim recognize it as alias of S
    def _visit_clifford(
        self, state: lowering.State[Node], name: str, node
    ) -> ir.Statement:
        if "DAG" in name:
            inst_name = name.rstrip("_DAG")
            dagger = True
        else:
            inst_name = name
            dagger = False

        return getattr(gate, inst_name)(
            targets=self._get_multiple_qubit_or_rec_ssa(
                state, node, node.targets_copy()
            ),
            dagger=dagger,
        )

    def visit_X(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_clifford(state, "X", node)

    def visit_Y(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_clifford(state, "Y", node)

    def visit_Z(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_clifford(state, "Z", node)

    def visit_I(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_clifford(state, "Identity", node)

    def visit_H(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_clifford(state, "H", node)

    def visit_S(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_clifford(state, "S", node)

    def visit_S_DAG(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_clifford(state, "S_DAG", node)

    def visit_SQRT_X(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_clifford(state, "SqrtX", node)

    def visit_SQRT_Y(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_clifford(state, "SqrtY", node)

    def visit_SQRT_X_DAG(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_clifford(state, "SqrtX_DAG", node)

    def visit_SQRT_Y_DAG(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_clifford(state, "SqrtY_DAG", node)

    def visit_SWAP(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_clifford(state, "Swap", node)

    # gate: 2Q gate-------------------------:
    def _visit_2q_gate(
        self, state: lowering.State[Node], name: str, node
    ) -> ir.Statement:
        all_targets = self._get_multiple_qubit_or_rec_ssa(
            state, node, node.targets_copy()
        )
        return getattr(gate, name)(
            controls=all_targets[::2],
            targets=all_targets[1::2],
            dagger=False,
        )

    def visit_CX(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_2q_gate(state, "CX", node)

    def visit_CY(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_2q_gate(state, "CY", node)

    def visit_CZ(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_2q_gate(state, "CZ", node)

    # gate: SPP-------------------------:
    def visit_SPP(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return getattr(gate, "SPP")(
            targets=self._get_pauli_string_targets_ssa(
                state, node, node.targets_copy()
            ),
            dagger=False,
        )

    def visit_SPP_DAG(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return getattr(gate, "SPP")(
            targets=self._get_pauli_string_targets_ssa(
                state, node, node.targets_copy()
            ),
            dagger=True,
        )

    # noise: ..........................................:
    def _visit_single_p_error(
        self, state: lowering.State[Node], name: str, node
    ) -> ir.Statement:
        return getattr(noise, name)(
            p=self._get_optional_float_arg_ssa(state, node.gate_args_copy()),
            targets=self._get_multiple_qubit_or_rec_ssa(
                state, node, node.targets_copy()
            ),
        )

    def visit_X_ERROR(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_single_p_error(state, "XError", node)

    def visit_Y_ERROR(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_single_p_error(state, "YError", node)

    def visit_Z_ERROR(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_single_p_error(state, "ZError", node)

    def visit_DEPOLARIZE1(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_single_p_error(state, "Depolarize1", node)

    def visit_DEPOLARIZE2(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        return self._visit_single_p_error(state, "Depolarize2", node)

    # noise pauli channel 1 & 2............................:
    def visit_PAULI_CHANNEL_1(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        args = self._get_float_args_ssa(state, node.gate_args_copy())
        return getattr(noise, "PauliChannel1")(
            px=args[0],
            py=args[1],
            pz=args[2],
            targets=self._get_multiple_qubit_or_rec_ssa(
                state, node, node.targets_copy()
            ),
        )

    def visit_PAULI_CHANNEL_2(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
        args = self._get_float_args_ssa(state, node.gate_args_copy())
        return getattr(noise, "PauliChannel2")(
            pix=args[0],
            piy=args[1],
            piz=args[2],
            pxi=args[3],
            pxx=args[4],
            pxy=args[5],
            pxz=args[6],
            pyi=args[7],
            pyx=args[8],
            pyy=args[9],
            pyz=args[10],
            pzi=args[11],
            pzx=args[12],
            pzy=args[13],
            pzz=args[14],
            targets=self._get_multiple_qubit_or_rec_ssa(
                state, node, node.targets_copy()
            ),
        )

    def visit_I_ERROR(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement | None:
        # I_ERROR represents any noise supported by external simulators but not stim
        # Parse tag
        tag_parts = node.tag.split(";", maxsplit=1)[0].split(":", maxsplit=1)
        nonstim_name = tag_parts[0]
        nonce = 0
        if len(tag_parts) == 2:
            try:
                nonce = int(tag_parts[1])
            except ValueError:
                # String was not an integer
                if self.error_unknown_nonstim:
                    raise lowering.BuildError(
                        f"Unsupported non-stim tag format: {node.tag!r} ({node!r})"
                    )
                return
        if nonstim_name not in self.nonstim_noise_ops and self.error_unknown_nonstim:
            raise lowering.BuildError(
                f"Unknown non-stim statement name: {nonstim_name!r} ({node!r})"
            )
        statement_cls = self.nonstim_noise_ops.get(nonstim_name)
        if statement_cls is not None:
            if issubclass(statement_cls, noise.NonStimCorrelatedError):
                stmt = statement_cls(
                    nonce=nonce,
                    probs=self._get_float_args_ssa(state, node.gate_args_copy()),
                    targets=self._get_multiple_qubit_or_rec_ssa(
                        state, node, node.targets_copy()
                    ),
                )
            else:
                stmt = statement_cls(
                    probs=self._get_float_args_ssa(state, node.gate_args_copy()),
                    targets=self._get_multiple_qubit_or_rec_ssa(
                        state, node, node.targets_copy()
                    ),
                )
        return stmt

    def visit_CircuitInstruction(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> lowering.Result:
        name = node.name.upper()

        match name:
            # Stim name abbreviation substitutions to canonical name
            case "R":
                name = "RZ"
            case "M":
                name = "MZ"

        # dispatch base on name (capital)
        inst = getattr(self, f"visit_{name}", None)
        if inst is not None:
            stmt = inst(state, node)
            if stmt is not None:
                state.current_frame.push(stmt)
        else:
            if not self.ignore_unknown_stim:
                raise lowering.BuildError(
                    f"Unsupported stim instruction: {type(node)} ({node!r})"
                )
