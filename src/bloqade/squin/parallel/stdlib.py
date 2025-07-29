from typing import Any, TypeVar

from kirin import ir
from kirin.prelude import structural_no_opt
from kirin.dialects import ilist

from bloqade.types import Qubit

from .. import op as _op, qubit as _qubit


@ir.dialect_group(structural_no_opt.union([_qubit, _op]))
def broadcast(self):
    def run_pass(method):
        pass

    return run_pass


@broadcast
def x(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.x()
    _qubit.broadcast(op, qubits)


@broadcast
def y(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.y()
    _qubit.broadcast(op, qubits)


@broadcast
def z(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.z()
    _qubit.broadcast(op, qubits)


@broadcast
def sqrt_x(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.sqrt_x()
    _qubit.broadcast(op, qubits)


@broadcast
def sqrt_y(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.sqrt_y()
    _qubit.broadcast(op, qubits)


@broadcast
def sqrt_z(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.s()
    _qubit.broadcast(op, qubits)


@broadcast
def h(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.h()
    _qubit.broadcast(op, qubits)


@broadcast
def s(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.s()
    _qubit.broadcast(op, qubits)


@broadcast
def t(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.t()
    _qubit.broadcast(op, qubits)


@broadcast
def p0(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.p0()
    _qubit.broadcast(op, qubits)


@broadcast
def p1(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.p1()
    _qubit.broadcast(op, qubits)


@broadcast
def spin_n(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.spin_n()
    _qubit.broadcast(op, qubits)


@broadcast
def spin_p(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.spin_p()
    _qubit.broadcast(op, qubits)


@broadcast
def reset(qubits: ilist.IList[Qubit, Any]) -> None:
    op = _op.reset()
    _qubit.broadcast(op, qubits)


N = TypeVar("N")


@broadcast
def cx(controls: ilist.IList[Qubit, N], targets: ilist.IList[Qubit, N]) -> None:
    op = _op.cx()
    _qubit.broadcast(op, controls, targets)


@broadcast
def cy(controls: ilist.IList[Qubit, N], targets: ilist.IList[Qubit, N]) -> None:
    op = _op.cy()
    _qubit.broadcast(op, controls, targets)


@broadcast
def cz(controls: ilist.IList[Qubit, N], targets: ilist.IList[Qubit, N]) -> None:
    op = _op.cz()
    _qubit.broadcast(op, controls, targets)


@broadcast
def ch(controls: ilist.IList[Qubit, N], targets: ilist.IList[Qubit, N]) -> None:
    op = _op.ch()
    _qubit.broadcast(op, controls, targets)
