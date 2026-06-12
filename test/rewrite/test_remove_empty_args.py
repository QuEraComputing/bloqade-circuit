import bloqade.squin as squin
from bloqade.rewrite.passes.remove_empty_args import (
    RemoveEmptyArgGates,
    _has_empty_ilist_input,
)
from kirin.dialects.func.stmts import Invoke


def _invoke_names(mt):
    return [s.callee.sym_name for s in mt.code.walk() if isinstance(s, Invoke)]


def test_empty_broadcast_detected():
    @squin.kernel
    def k():
        squin.broadcast.x([])
    invokes = [s for s in k.code.walk() if isinstance(s, Invoke) and s.callee.sym_name == "x"]
    assert invokes
    assert _has_empty_ilist_input(invokes[0])


def test_nonempty_broadcast_not_detected():
    @squin.kernel
    def k():
        q = squin.qalloc(2)
        squin.broadcast.h(q)
    invokes = [s for s in k.code.walk() if isinstance(s, Invoke) and s.callee.sym_name == "h"]
    assert invokes
    assert not _has_empty_ilist_input(invokes[0])


def test_removes_empty_broadcast():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.h(q)
        squin.broadcast.x([])

    result = RemoveEmptyArgGates(main.dialects)(main)
    assert result.has_done_something
    names = _invoke_names(main)
    assert "x" not in names
    assert "h" in names


def test_removes_multiple_empty_broadcasts():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.broadcast.h(q)
        squin.broadcast.x([])
        squin.broadcast.y([])
        squin.broadcast.z([])

    result = RemoveEmptyArgGates(main.dialects)(main)
    assert result.has_done_something
    names = _invoke_names(main)
    for gate in ("x", "y", "z"):
        assert gate not in names
    assert "h" in names


def test_preserves_nonempty():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.h(q)

    result = RemoveEmptyArgGates(main.dialects)(main)
    assert not result.has_done_something


def test_idempotent():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.x([])

    RemoveEmptyArgGates(main.dialects)(main)
    result2 = RemoveEmptyArgGates(main.dialects)(main)
    assert not result2.has_done_something


def test_dce_cleans_dead_constant():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.x([])

    RemoveEmptyArgGates(main.dialects)(main)

    from kirin.dialects.py import Constant as PyConstant
    from kirin.dialects.ilist.runtime import IList
    dead = [s for s in main.code.walk()
            if isinstance(s, PyConstant) and isinstance(s.value, IList) and len(s.value) == 0]
    assert not dead


def test_issue_516_example():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.h(q)
        squin.broadcast.x([])

    RemoveEmptyArgGates(main.dialects)(main)
    names = _invoke_names(main)
    assert "x" not in names
    assert "h" in names
