from typing import TypeVar

from kirin import interp
from kirin.analysis import ForwardFrame
from kirin.dialects import ilist

from bloqade.squin import noise
from bloqade.analysis.address import Address, AddressReg
from bloqade.analysis.fidelity import FidelityAnalysis
from bloqade.analysis.address.lattice import StaticContainer

T = TypeVar("T")


@noise.dialect.register(key="circuit.fidelity")
class __NoiseMethods(interp.MethodTable):

    @interp.impl(noise.stmts.SingleQubitPauliChannel)
    def single_qubit_pauli_channel(
        self,
        interp_: FidelityAnalysis,
        frame: ForwardFrame[Address],
        stmt: noise.stmts.SingleQubitPauliChannel,
    ):
        px = interp_.get_const_value(frame.get(stmt.px), float)
        py = interp_.get_const_value(frame.get(stmt.py), float)
        pz = interp_.get_const_value(frame.get(stmt.pz), float)

        if px is None or py is None or pz is None:
            return ()

        addresses = frame.get(stmt.qubits)
        if not isinstance(addresses, AddressReg):
            return ()

        fidelity = 1 - (px + py + pz)
        interp_.update_fidelities(interp_.gate_fidelities, fidelity, addresses)

        return ()

    @interp.impl(noise.stmts.TwoQubitPauliChannel)
    def two_qubit_pauli_channel(
        self,
        interp_: FidelityAnalysis,
        frame: ForwardFrame[Address],
        stmt: noise.stmts.TwoQubitPauliChannel,
    ):
        probabilities = interp_.get_const_value(
            frame.get(stmt.probabilities), (list, tuple, ilist.IList)
        )

        if probabilities is None:
            return ()

        control_addresses = frame.get(stmt.controls)
        target_addresses = frame.get(stmt.targets)

        if not isinstance(control_addresses, AddressReg) or not isinstance(
            target_addresses, AddressReg
        ):
            return ()

        # NOTE: total noise probability is the sum over all probabilities where non-identity is applied
        p_control = 0.0
        p_target = 0.0

        # NOTE: not elegant, but easy to ensure correctness
        for i, (p, pauli_op) in enumerate(
            zip(
                probabilities,
                (
                    "IX",
                    "IY",
                    "IS",
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
                ),
            )
        ):

            if pauli_op[0] != "I":
                p_control += p

            if pauli_op[1] != "I":
                p_target += p

        fidelity_control = 1 - p_control
        fidelity_target = 1 - p_target

        interp_.update_fidelities(
            interp_.gate_fidelities, fidelity_control, control_addresses
        )
        interp_.update_fidelities(
            interp_.gate_fidelities, fidelity_target, target_addresses
        )

        return ()

    @interp.impl(noise.stmts.Depolarize)
    def depolarize(
        self,
        interp_: FidelityAnalysis,
        frame: ForwardFrame[Address],
        stmt: noise.stmts.Depolarize,
    ):
        p = interp_.get_const_value(frame.get(stmt.p), float)

        if p is None:
            return ()

        addresses = frame.get(stmt.qubits)
        if not isinstance(addresses, AddressReg):
            return ()

        fidelity = 1 - p
        interp_.update_fidelities(interp_.gate_fidelities, fidelity, addresses)

        return ()

    @interp.impl(noise.stmts.Depolarize2)
    def depolarize2(
        self,
        interp_: FidelityAnalysis,
        frame: ForwardFrame[Address],
        stmt: noise.stmts.Depolarize2,
    ):
        p = interp_.get_const_value(frame.get(stmt.p), float)

        if p is None:
            return ()

        control_addresses = frame.get(stmt.controls)
        target_addresses = frame.get(stmt.targets)

        if not isinstance(control_addresses, AddressReg) or not isinstance(
            target_addresses, AddressReg
        ):
            return ()

        # NOTE: there are 15 potential noise operators, 3 of which apply identity to the first and 3 that apply identity to the second qubit
        # leaving 12 / 15 noise channels for each qubit to decrease the fidelity

        fidelity = 1 - 12.0 * p / 15.0

        interp_.update_fidelities(interp_.gate_fidelities, fidelity, control_addresses)
        interp_.update_fidelities(interp_.gate_fidelities, fidelity, target_addresses)

        return ()

    @interp.impl(noise.stmts.QubitLoss)
    def qubit_loss(
        self,
        interp_: FidelityAnalysis,
        frame: ForwardFrame[Address],
        stmt: noise.stmts.QubitLoss,
    ):
        p = interp_.get_const_value(frame.get(stmt.p), float)

        if p is None:
            return ()

        survival = 1 - p
        addresses = frame.get(stmt.qubits)
        if not isinstance(addresses, AddressReg):
            return ()

        interp_.update_fidelities(
            interp_.qubit_survival_fidelities, survival, addresses
        )

        return ()

    @interp.impl(noise.stmts.CorrelatedQubitLoss)
    def correlated_qubit_loss(
        self,
        interp_: FidelityAnalysis,
        frame: ForwardFrame[Address],
        stmt: noise.stmts.CorrelatedQubitLoss,
    ):
        p = interp_.get_const_value(frame.get(stmt.p), float)

        if p is None:
            return ()

        addresses = frame.get(stmt.qubits)

        if not isinstance(addresses, StaticContainer):
            return ()

        # NOTE: p is the probability with which an entire atom group is lost
        # therefore, the fidelity of each atom decreases according to the following
        fidelity = 1 - p

        for address in addresses.data:
            if not isinstance(address, AddressReg):
                continue

            interp_.update_fidelities(
                interp_.qubit_survival_fidelities, fidelity, address
            )

        return ()
