from kirin.dialects.func.stmts import Invoke

from bloqade import squin
from bloqade.rewrite.passes import RemoveEmptyArgGates


def _invokes(mt):
    return [stmt.callee.sym_name for stmt in mt.code.walk() if isinstance(stmt, Invoke)]


def test_removes_empty_broadcast_gate():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.h(q)
        squin.broadcast.x([])

    RemoveEmptyArgGates(main.dialects)(main)

    invokes = _invokes(main)
    assert "x" not in invokes
    assert "h" in invokes


def test_removes_empty_noise_and_controlled():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.depolarize(0.1, [])
        squin.broadcast.cx([], [])
        squin.broadcast.h(q)

    RemoveEmptyArgGates(main.dialects)(main)

    invokes = _invokes(main)
    assert "depolarize" not in invokes
    assert "cx" not in invokes
    assert "h" in invokes


def test_removes_unused_empty_measurement():
    @squin.kernel
    def main():
        squin.measure([])

    RemoveEmptyArgGates(main.dialects)(main)

    assert "measure" not in _invokes(main)


def test_keeps_non_empty_gates():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.h(q)
        squin.broadcast.cx([q[0]], [q[1]])

    RemoveEmptyArgGates(main.dialects)(main)

    invokes = _invokes(main)
    assert "h" in invokes
    assert "cx" in invokes


def test_keeps_used_measurement():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        return squin.measure(q)

    RemoveEmptyArgGates(main.dialects)(main)

    assert "measure" in _invokes(main)


def test_dce_removes_emptied_function_call():
    @squin.kernel
    def sub():
        squin.broadcast.x([])

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.broadcast.h(q)
        sub()

    RemoveEmptyArgGates(main.dialects)(main)

    invokes = _invokes(main)
    assert "sub" not in invokes
    assert "h" in invokes
