from typing import Any, Optional
from dataclasses import dataclass

from kirin.dialects import ilist

from bloqade.pyqrack import PyQrackQubit


@dataclass
class OperatorRuntimeABC:
    target_index: int

    def apply(self, qubits: ilist.IList[PyQrackQubit, Any]) -> None:
        raise NotImplementedError(
            "Operator runtime base class should not be called directly, override the method"
        )


@dataclass
class OperatorRuntime(OperatorRuntimeABC):
    method_name: str
    ctrl_index: Optional[list[int]] = None

    def apply(
        self,
        qubits: ilist.IList[PyQrackQubit, Any],
    ):
        target_qubit = qubits[self.target_index]
        if self.ctrl_index is not None:
            ctrls = [qubits[i].addr for i in self.ctrl_index]
            getattr(target_qubit.sim_reg, self.method_name)(ctrls, target_qubit.addr)
        else:
            getattr(target_qubit.sim_reg, self.method_name)(target_qubit.addr)


@dataclass
class ProjectorRuntime(OperatorRuntimeABC):
    to_state: bool

    def apply(
        self,
        qubits: ilist.IList[PyQrackQubit, Any],
    ):
        target_qubit = qubits[self.target_index]
        target_qubit.sim_reg.force_m(target_qubit.addr, self.to_state)


@dataclass
class IdentityRuntime(OperatorRuntimeABC):
    # TODO: do we even need sites? The apply never does anything
    sites: int

    def apply(self, qubits: ilist.IList[PyQrackQubit, Any]):
        pass
