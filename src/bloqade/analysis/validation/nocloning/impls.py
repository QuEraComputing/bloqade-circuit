from kirin import interp
from kirin.analysis import ForwardFrame
from kirin.dialects import scf, func

from bloqade.analysis.address.lattice import (
    Unknown,
    AddressReg,
    UnknownReg,
    AddressQubit,
    PartialIList,
    PartialTuple,
    UnknownQubit,
)

from .lattice import May, Top, Must, Bottom, QubitValidation
from .analysis import _NoCloningAnalysis


@scf.dialect.register(key="validate.nocloning")
class Scf(interp.MethodTable):
    @interp.impl(scf.IfElse)
    def if_else(
        self,
        interp_: _NoCloningAnalysis,
        frame: ForwardFrame[QubitValidation],
        stmt: scf.IfElse,
    ):
        try:
            cond_validation = frame.get(stmt.cond)
        except Exception:
            cond_validation = Top()

        with interp_.new_frame(stmt, has_parent_access=True) as then_frame:
            interp_.frame_call_region(then_frame, stmt, stmt.then_body, cond_validation)

        then_state = Bottom()
        for node, val in then_frame.entries.items():
            if isinstance(val, (Must, May)):
                then_state = then_state.join(val)

        else_state = Bottom()
        if stmt.else_body:
            with interp_.new_frame(stmt, has_parent_access=True) as else_frame:
                interp_.frame_call_region(
                    else_frame, stmt, stmt.else_body, cond_validation
                )

            for node, val in else_frame.entries.items():
                if isinstance(val, (Must, May)):
                    else_state = else_state.join(val)

        merged = then_state.join(else_state)

        if isinstance(merged, May):
            then_has = not isinstance(then_state, Bottom)
            else_has = not isinstance(else_state, Bottom)

            if then_has and not else_has:
                new_violations = frozenset(
                    (gate, ", when condition is true") for gate, _ in merged.violations
                )
                merged = May(violations=new_violations)
            elif else_has and not then_has:
                new_violations = frozenset(
                    (gate, ", when condition is false") for gate, _ in merged.violations
                )
                merged = May(violations=new_violations)

        return (merged,)


@func.dialect.register(key="validate.nocloning")
class Func(interp.MethodTable):
    @interp.impl(func.Invoke)
    def invoke_(
        self,
        interp_: _NoCloningAnalysis,
        frame: ForwardFrame[QubitValidation],
        stmt: func.Invoke,
    ):
        if not isinstance(stmt, func.Invoke):
            return tuple(Bottom() for _ in stmt.results)

        address_frame = interp_._address_frame
        if address_frame is None:
            return tuple(Top() for _ in stmt.results)

        concrete_addrs: list[int] = []
        has_unknown = False
        has_qubit_args = False
        unknown_arg_names: list[str] = []

        for arg in stmt.args:
            addr = address_frame.get(arg)
            match addr:
                case AddressQubit(data=qubit_addr):
                    has_qubit_args = True
                    concrete_addrs.append(qubit_addr)
                case AddressReg(data=addrs):
                    has_qubit_args = True
                    concrete_addrs.extend(addrs)
                case (
                    UnknownQubit()
                    | UnknownReg()
                    | PartialIList()
                    | PartialTuple()
                    | Unknown()
                ):
                    has_qubit_args = True
                    has_unknown = True
                    arg_name = interp_._get_source_name(arg)
                    unknown_arg_names.append(arg_name)
                case _:
                    pass

        if not has_qubit_args:
            return tuple(Bottom() for _ in stmt.results)

        seen: set[int] = set()
        violations: set[tuple[int, str]] = set()
        s_name = getattr(stmt.callee, "sym_name", "<unknown>")
        gate_name = s_name.upper()

        for qubit_addr in concrete_addrs:
            if qubit_addr in seen:
                violations.add((qubit_addr, gate_name))
            seen.add(qubit_addr)

        if violations:
            current_errors = interp_.get_validation_errors()
            # NOTE: verify violation by stepping into the function
            _ = interp_.call(
                stmt.callee.code,
                interp_.method_self(stmt.callee),
                *frame.get_values(stmt.inputs),
            )

            if len(interp_.get_validation_errors()) > len(current_errors):
                # NOTE: there was a new error added
                usage = Must(violations=frozenset(violations))
            else:
                # NOTE: we're actually fine
                usage = Bottom()
        elif has_unknown:
            args_str = " == ".join(unknown_arg_names)
            if len(unknown_arg_names) > 1:
                condition = f", when {args_str}"
            else:
                condition = f", with unknown argument {args_str}"

            usage = May(violations=frozenset([(gate_name, condition)]))
        else:
            usage = Bottom()

        return tuple(usage for _ in stmt.results)
