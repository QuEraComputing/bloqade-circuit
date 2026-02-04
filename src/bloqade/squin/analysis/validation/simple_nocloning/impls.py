from kirin import interp
from kirin.lattice import EmptyLattice
from kirin.analysis import ForwardFrame

from bloqade.squin import gate, noise
from bloqade.analysis.address.lattice import AddressReg, PartialIList
from bloqade.analysis.validation.simple_nocloning import _FlatKernelNoCloningAnalysis


@gate.dialect.register(key="validate.nocloning.flatkernel")
class GateMethods(interp.MethodTable):
    @interp.impl(gate.stmts.X)
    @interp.impl(gate.stmts.Y)
    @interp.impl(gate.stmts.Z)
    @interp.impl(gate.stmts.H)
    @interp.impl(gate.stmts.S)
    @interp.impl(gate.stmts.T)
    @interp.impl(gate.stmts.Rx)
    @interp.impl(gate.stmts.Ry)
    @interp.impl(gate.stmts.Rz)
    def single_qubit_gate(
        self,
        interp_: _FlatKernelNoCloningAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: gate.stmts.SingleQubitGate,
    ):
        if interp_._address_frame is None:
            return

        qubit_addrs = interp_._address_frame.get(stmt.qubits)

        if not isinstance(qubit_addrs, AddressReg):
            return

        unique_addrs = set(qubit_addrs.data)
        if len(qubit_addrs.data) == len(unique_addrs):
            return

        interp_.collect_errors(stmt, list(qubit_addrs.data))

    @interp.impl(gate.stmts.CX)
    @interp.impl(gate.stmts.CY)
    @interp.impl(gate.stmts.CZ)
    def controlled_gate(
        self,
        interp_: _FlatKernelNoCloningAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: gate.stmts.ControlledGate,
    ):

        if interp_._address_frame is None:
            return

        control_addrs = interp_._address_frame.get(stmt.controls)
        target_addrs = interp_._address_frame.get(stmt.targets)

        if not isinstance(control_addrs, AddressReg) or not isinstance(
            target_addrs, AddressReg
        ):
            return

        all_addrs = list(control_addrs.data) + list(target_addrs.data)
        unique_addrs = set(all_addrs)

        if len(all_addrs) == len(unique_addrs):
            return

        interp_.collect_errors(stmt, all_addrs)


@noise.dialect.register(key="validate.nocloning.flatkernel")
class NoiseMethods(interp.MethodTable):
    @interp.impl(noise.stmts.Depolarize)
    @interp.impl(noise.stmts.SingleQubitPauliChannel)
    @interp.impl(noise.stmts.QubitLoss)
    def single_qubit_noise_channel(
        self,
        interp_: _FlatKernelNoCloningAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: (
            noise.stmts.SingleQubitPauliChannel
            | noise.stmts.Depolarize
            | noise.stmts.QubitLoss
        ),
    ):
        if interp_._address_frame is None:
            return

        qubit_addrs = interp_._address_frame.get(stmt.qubits)

        if not isinstance(qubit_addrs, AddressReg):
            return

        if len(qubit_addrs.data) == len(set(qubit_addrs.data)):
            return

        interp_.collect_errors(stmt, list(qubit_addrs.data))

    @interp.impl(noise.stmts.Depolarize2)
    @interp.impl(noise.stmts.TwoQubitPauliChannel)
    def two_qubit_noise_channel(
        self,
        interp_: _FlatKernelNoCloningAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: noise.stmts.Depolarize2 | noise.stmts.TwoQubitPauliChannel,
    ):
        if interp_._address_frame is None:
            return

        control_addrs = interp_._address_frame.get(stmt.controls)
        target_addrs = interp_._address_frame.get(stmt.targets)

        if not isinstance(control_addrs, AddressReg) or not isinstance(
            target_addrs, AddressReg
        ):
            return

        all_addrs = list(control_addrs.data) + list(target_addrs.data)

        if len(all_addrs) == len(set(all_addrs)):
            return

        interp_.collect_errors(stmt, all_addrs)

    @interp.impl(noise.stmts.CorrelatedQubitLoss)
    def correlated_loss(
        self,
        interp_: _FlatKernelNoCloningAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: noise.stmts.CorrelatedQubitLoss,
    ):
        if interp_._address_frame is None:
            return

        qubit_addrs = interp_._address_frame.get(stmt.qubits)

        if not isinstance(qubit_addrs, PartialIList):
            return

        all_addresses = []
        for group_addrs in qubit_addrs.data:
            if not isinstance(group_addrs, AddressReg):
                continue
            all_addresses.extend(group_addrs.data)

        if len(all_addresses) == len(set(all_addresses)):
            return

        interp_.collect_errors(stmt, all_addresses)
