import io
import math

from bloqade import stim, squin as sq
from bloqade.squin import kernel
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass


def codegen(mt):
    buf = io.StringIO()
    emit = EmitStimMain(dialects=stim.main, io=buf)
    emit.initialize()
    emit.run(mt)
    return buf.getvalue().strip()


def test_t_gate():
    @kernel
    def test():
        q = sq.qalloc(2)
        sq.t(q[0])
        sq.t_adj(q[1])
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "S[T] 0\nS_DAG[T] 1"


def test_rx_gate():
    @kernel
    def test():
        q = sq.qalloc(1)
        sq.rx(0.3 * math.pi, q[0])
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "I[R_X(theta=0.3*pi)] 0"


def test_ry_gate():
    @kernel
    def test():
        q = sq.qalloc(1)
        sq.ry(0.25 * math.pi, q[0])
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "I[R_Y(theta=0.25*pi)] 0"


def test_rz_gate():
    @kernel
    def test():
        q = sq.qalloc(1)
        sq.rz(-0.5 * math.pi, q[0])
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "I[R_Z(theta=-0.5*pi)] 0"


def test_u3_non_clifford():
    @kernel
    def test():
        q = sq.qalloc(1)
        sq.u3(0.3 * math.pi, 0.24 * math.pi, 0.49 * math.pi, q[0])
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "I[U3(theta=0.3*pi, phi=0.24*pi, lambda=0.49*pi)] 0"


def test_u3_clifford_still_works():
    @kernel
    def test():
        q = sq.qalloc(1)
        sq.u3(0.25 * math.tau, 0.0 * math.tau, 0.5 * math.tau, q[0])
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "H 0"


def test_mixed_gates():
    @kernel
    def test():
        q = sq.qalloc(3)
        sq.h(q[0])
        sq.t(q[1])
        sq.rx(0.1 * math.pi, q[2])
        sq.cx(q[0], q[1])
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "H 0\nS[T] 1\nI[R_X(theta=0.1*pi)] 2\nCX 0 1"


def test_broadcast_t_gate():
    @kernel
    def test():
        q = sq.qalloc(3)
        sq.broadcast.t(q)
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "S[T] 0 1 2"


def test_broadcast_t_adj_gate():
    @kernel
    def test():
        q = sq.qalloc(2)
        sq.broadcast.t_adj(q)
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "S_DAG[T] 0 1"


def test_broadcast_rx_gate():
    @kernel
    def test():
        q = sq.qalloc(3)
        sq.broadcast.rx(0.3 * math.pi, q)
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "I[R_X(theta=0.3*pi)] 0 1 2"


def test_broadcast_ry_gate():
    @kernel
    def test():
        q = sq.qalloc(2)
        sq.broadcast.ry(0.25 * math.pi, q)
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "I[R_Y(theta=0.25*pi)] 0 1"


def test_broadcast_rz_gate():
    @kernel
    def test():
        q = sq.qalloc(2)
        sq.broadcast.rz(-0.5 * math.pi, q)
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "I[R_Z(theta=-0.5*pi)] 0 1"


def test_broadcast_u3_non_clifford():
    @kernel
    def test():
        q = sq.qalloc(2)
        sq.broadcast.u3(0.3 * math.pi, 0.24 * math.pi, 0.49 * math.pi, q)
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "I[U3(theta=0.3*pi, phi=0.24*pi, lambda=0.49*pi)] 0 1"


def test_broadcast_u3_clifford():
    @kernel
    def test():
        q = sq.qalloc(2)
        sq.broadcast.u3(0.25 * math.tau, 0.0 * math.tau, 0.5 * math.tau, q)
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == "H 0 1"
