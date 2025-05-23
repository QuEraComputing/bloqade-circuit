"""One-to-one lowering routine from stim circuit to a stim-dialect kirin kernel."""

from typing import TYPE_CHECKING, Any, Union
from dataclasses import field, dataclass

import kirin
from kirin import ir, lowering
from kirin.dialects import func

import bloqade.stim as kstim
from bloqade.stim.dialects import noise, collapse, auxiliary  # , gate

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
    nonstim_noise_ops: dict[str, kirin.ir.Statement] = {},
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

    def _get_qubit_targets_ssa(
        self, state: lowering.State[Node], node: Node, targets: list[Node]
    ):
        out = tuple(
            self.lower_literal(state, targ.qubit_value)
            for targ in targets
            if targ.is_qubit_target
        )
        if len(out) != len(targets):
            raise lowering.BuildError(
                f"Unexpected stim targets on instruction (expected qubit targets): {node!r}"
            )
        return out

    def _get_rec_targets_ssa(
        self, state: lowering.State[Node], node: Node, targets: list[Node]
    ):
        def make_record(id_val):
            lit = self.lower_literal(state, id_val)
            stmt = auxiliary.GetRecord(id=lit)
            state.current_frame.push(stmt)
            return stmt.result

        out = tuple(
            make_record(targ.value)
            for targ in targets
            if targ.is_measurement_record_target
        )
        if len(out) != len(targets):
            raise lowering.BuildError(
                f"Unexpected stim targets on instruction (expected measurement record targets): {node!r}"
            )
        return out

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

    def _visit_reset(
        self, state: lowering.State[Node], name: str, node
    ) -> ir.Statement:
        return getattr(collapse, name)(
            targets=self._get_qubit_targets_ssa(state, node, node.targets_copy())
        )

    def visit_RZ(self, state: lowering.State[Node], node: "stim.RZ") -> ir.Statement:
        return self._visit_reset(state, "RZ", node)

    def visit_RX(self, state: lowering.State[Node], node: "stim.RX") -> ir.Statement:
        return self._visit_reset(state, "RX", node)

    def visit_RY(self, state: lowering.State[Node], node: "stim.RY") -> ir.Statement:
        return self._visit_reset(state, "RY", node)

    def visit_TICK(
        self, state: lowering.State[Node], node: "stim.TICK"
    ) -> ir.Statement:
        return auxiliary.Tick()

    def _visit_measure(
        self, state: lowering.State[Node], name: str, node
    ) -> ir.Statement:
        return getattr(collapse, name)(
            p=self._get_optional_float_arg_ssa(state, node.gate_args_copy()),
            targets=self._get_qubit_targets_ssa(state, node, node.targets_copy()),
        )

    def visit_MX(self, state: lowering.State[Node], node: "stim.MX") -> ir.Statement:
        return self._visit_measure(state, "MX", node)

    def visit_MY(self, state: lowering.State[Node], node: "stim.MY") -> ir.Statement:
        return self._visit_measure(state, "MY", node)

    def visit_MZ(self, state: lowering.State[Node], node: "stim.MZ") -> ir.Statement:
        return self._visit_measure(state, "MZ", node)

    def visit_MXX(self, state: lowering.State[Node], node: "stim.MXX") -> ir.Statement:
        return self._visit_measure(state, "MXX", node)

    def visit_MYY(self, state: lowering.State[Node], node: "stim.MYY") -> ir.Statement:
        return self._visit_measure(state, "MYY", node)

    def visit_MZZ(self, state: lowering.State[Node], node: "stim.MZZ") -> ir.Statement:
        return self._visit_measure(state, "MZZ", node)

    def visit_DETECTOR(
        self, state: lowering.State[Node], node: "stim.Detector"
    ) -> ir.Statement:
        return auxiliary.Detector(
            coord=self._get_float_args_ssa(state, node.gate_args_copy()),
            targets=self._get_rec_targets_ssa(state, node, node.targets_copy()),
        )

    def visit_OBSERVABLE_INCLUDE(
        self, state: lowering.State[Node], node: "stim.ObservableInclude"
    ) -> ir.Statement:
        return auxiliary.ObservableInclude(
            idx=self._get_optional_int_arg_ssa(state, node.gate_args_copy()),
            targets=self._get_rec_targets_ssa(state, node, node.targets_copy()),
        )

    def visit_I_ERROR(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> ir.Statement:
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
                    targets=self._get_rec_targets_ssa(state, node, node.targets_copy()),
                )
            else:
                stmt = statement_cls(
                    probs=self._get_float_args_ssa(state, node.gate_args_copy()),
                    targets=self._get_rec_targets_ssa(state, node, node.targets_copy()),
                )
        return stmt

    def visit_CircuitInstruction(
        self, state: lowering.State[Node], node: "stim.CircuitInstruction"
    ) -> lowering.Result:
        name = node.name.upper()
        # gate_args = node.gate_args_copy()
        # targets = node.targets_copy()
        # _target_groups = node.target_groups()  # Uncommonly used by instructions
        # _num_measurements = node.num_measurements  # Uncommonly used by instructions
        # tag = (
        #     node.tag
        # )  # Used to store non-stim information about the circuit instruction

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

        # -----
        # match name:
        #     case "QUBIT_COORDS":
        #         # TODO: Add the QubitCoords instruction to the stim dialect
        #         # stmt = auxiliary.QubitCoords(
        #         #    coords=get_float_args_ssa(),
        #         #    targets=self._get_qubit_targets_ssa(),
        #         # )
        #         pass

        #     # TODO: Add many more stim gates...
        #     # ...
        #     # ...
