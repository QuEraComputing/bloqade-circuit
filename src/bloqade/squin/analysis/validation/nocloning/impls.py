from typing import Sequence

from kirin import ir, interp
from kirin.analysis import ForwardFrame

from bloqade.squin import gate
from bloqade.analysis.address import AddressReg
from bloqade.analysis.validation.nocloning.lattice import Must, Bottom, QubitValidation
from bloqade.analysis.validation.nocloning.analysis import _NoCloningAnalysis


@gate.dialect.register(key="validate.nocloning")
class GateMethods(interp.MethodTable):

    @interp.impl(gate.stmts.X)
    @interp.impl(gate.stmts.Y)
    @interp.impl(gate.stmts.Z)
    @interp.impl(gate.stmts.H)
    @interp.impl(gate.stmts.S)
    @interp.impl(gate.stmts.T)
    @interp.impl(gate.stmts.SqrtX)
    @interp.impl(gate.stmts.SqrtY)
    @interp.impl(gate.stmts.Rx)
    @interp.impl(gate.stmts.Ry)
    @interp.impl(gate.stmts.Rz)
    @interp.impl(gate.stmts.U3)
    def single_qubit_gate(
        self,
        interp_: _NoCloningAnalysis,
        frame: ForwardFrame[QubitValidation],
        stmt: gate.stmts.SingleQubitGate,
    ):
        if interp_._address_frame is None:
            return

        addr = interp_._address_frame.get_or_fallback_to_invoke(stmt.qubits)

        if not isinstance(addr, AddressReg):
            raise NotImplementedError("TODO: handle unknowns")

        return self._check_addresses_for_overlap(addr.data, interp_, stmt)

    @interp.impl(gate.stmts.CX)
    @interp.impl(gate.stmts.CY)
    @interp.impl(gate.stmts.CZ)
    def controlled_gate(
        self,
        interp_: _NoCloningAnalysis,
        frame: ForwardFrame[QubitValidation],
        stmt: gate.stmts.ControlledGate,
    ):
        if interp_._address_frame is None:
            return

        ctrl_addr = interp_._address_frame.get_or_fallback_to_invoke(stmt.controls)
        target_addr = interp_._address_frame.get_or_fallback_to_invoke(stmt.targets)

        if not isinstance(ctrl_addr, AddressReg) or not isinstance(
            target_addr, AddressReg
        ):
            raise NotImplementedError("TODO: handle unknowns")

        data = list(ctrl_addr.data) + list(target_addr.data)

        return self._check_addresses_for_overlap(data, interp_, stmt)

    def _check_addresses_for_overlap(
        self, data: Sequence[int], interp_: _NoCloningAnalysis, stmt: ir.Statement
    ):
        gate_name = stmt.name.upper()
        seen = set()
        violations = set()
        errors = []
        for qubit_addr in data:
            if qubit_addr in seen:
                errors.append(
                    ir.ValidationError(
                        stmt,
                        f"Gate {gate_name} applies to qubit {qubit_addr} more than once.",
                    )
                )
                violations.add((qubit_addr, gate_name))
            seen.add(qubit_addr)

        if violations:
            usage = Must(violations=frozenset(violations))
            for error in errors:
                interp_.add_validation_error(stmt, error)
        else:
            usage = Bottom()

        return tuple(usage for _ in stmt.results)
