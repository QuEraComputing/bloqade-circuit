import io

from kirin import ir
from kirin.rewrite import Walk

from bloqade import stim, squin
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.rewrite import InsertTicks
from bloqade.stim.passes import SquinToStimPass


def codegen(mt: ir.Method):
    buf = io.StringIO()
    emit = EmitStimMain(dialects=stim.main, io=buf)
    emit.initialize()
    emit.run(mt)
    return buf.getvalue().strip()


def _linear_kernel():
    @squin.kernel
    def test():
        ql = squin.qalloc(3)
        squin.broadcast.h(ql)
        squin.x(ql[0])
        squin.cx(ql[0], ql[1])
        squin.broadcast.measure(ql)
        return

    return test


def test_default_has_no_ticks():
    test = _linear_kernel()
    SquinToStimPass(test.dialects)(test)
    out = codegen(test)
    assert "TICK" not in out
    assert out == "\n".join(
        [
            "H 0 1 2",
            "X 0",
            "CX 0 1",
            "MZ(0.00000000) 0 1 2",
        ]
    )


def test_insert_ticks_separates_operations():
    test = _linear_kernel()
    SquinToStimPass(test.dialects, insert_ticks=True)(test)
    out = codegen(test)
    assert out == "\n".join(
        [
            "H 0 1 2",
            "TICK",
            "X 0",
            "TICK",
            "CX 0 1",
            "TICK",
            "MZ(0.00000000) 0 1 2",
            "TICK",
        ]
    )


def test_insert_ticks_preserves_record_indices():
    """TICKs are timing-only: detector/observable record indices must match
    the no-tick lowering exactly."""

    def make():
        @squin.kernel
        def main():
            q = squin.qalloc(4)
            squin.x(q[0])
            squin.cx(q[0], q[1])
            ms = squin.broadcast.measure(q)
            squin.set_detector([ms[0], ms[1]], coordinates=[0.0, 0.0])
            squin.set_observable(measurements=[ms[2]])
            return

        return main

    no_ticks = make()
    SquinToStimPass(no_ticks.dialects)(no_ticks)

    with_ticks = make()
    SquinToStimPass(with_ticks.dialects, insert_ticks=True)(with_ticks)

    def record_lines(out):
        return [
            line
            for line in out.splitlines()
            if line.startswith(("DETECTOR", "OBSERVABLE_INCLUDE"))
        ]

    assert record_lines(codegen(no_ticks)) == record_lines(codegen(with_ticks))


def test_insert_ticks_inside_repeat_block():
    @squin.kernel
    def test():
        qs = squin.qalloc(3)
        squin.broadcast.reset(qs)
        for _ in range(5):
            squin.broadcast.h(qs)
            squin.cz(control=qs[0], target=qs[1])

    SquinToStimPass(test.dialects, insert_ticks=True)(test)
    out = codegen(test)
    assert "REPEAT 5 {" in out
    # both operations inside the loop body are tick-separated
    body = out[out.index("{") : out.index("}")]
    assert body.count("TICK") == 2


def test_insert_ticks_rewrite_is_idempotent():
    test = _linear_kernel()
    SquinToStimPass(test.dialects, insert_ticks=True)(test)
    once = codegen(test)
    # running the standalone rewrite again must not add duplicate TICKs
    Walk(InsertTicks()).rewrite(test.code)
    assert codegen(test) == once
