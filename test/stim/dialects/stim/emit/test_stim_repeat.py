import io

from kirin import ir, types
from kirin.dialects import func

from bloqade import stim
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.dialects.cf.stmts import REPEAT
from bloqade.stim.dialects.auxiliary.stmts import ConstInt
from bloqade.stim.dialects.gate.stmts.clifford_1q import H, Z


def codegen(mt):
    # method should not have any arguments!
    buf = io.StringIO()
    emit = EmitStimMain(dialects=stim.main, io=buf)
    # emit.initialize()
    emit.run(mt)
    return buf.getvalue().strip()


def test_repeat_emit():

    num_iter = ConstInt(value=5)
    body = ir.Region(ir.Block([]))
    q0 = ConstInt(value=0)
    q1 = ConstInt(value=1)
    body.blocks[0].stmts.append(q0)
    body.blocks[0].stmts.append(q1)
    targets = (q0.result, q1.result)
    body.blocks[0].stmts.append(H(targets=targets))
    body.blocks[0].stmts.append(Z(targets=targets))
    repeat_stmt = REPEAT(count=num_iter.result, body=body)

    block = ir.Block()
    block.stmts.append(num_iter)
    block.stmts.append(repeat_stmt)

    block.args.append_from(types.MethodType, "self")
    gen_func = func.Function(
        sym_name="main",
        signature=func.Signature(
            inputs=(),
            output=types.NoneType,
        ),
        body=ir.Region(block),
    )

    result = codegen(gen_func)
    assert result == "REPEAT 5 {\n    H 0 1\n    Z 0 1\n}"
