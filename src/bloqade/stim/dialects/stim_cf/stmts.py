from kirin import ir, types
from kirin.decl import info, statement

from ._dialect import dialect


@statement(dialect=dialect, init=False)
class Repeat(ir.Statement):
    name = "repeat"
    traits = frozenset({ir.HasCFG(), ir.SSACFG()})
    count: ir.SSAValue = info.argument(type=types.Int)
    body: ir.Region = info.region(multi=False)

    def __init__(self, count: ir.SSAValue, body: ir.Region | None = None):
        if body is None:
            body = ir.Region(ir.Block())
        super().__init__(
            args=(count,),
            regions=(body,),
            result_types=(),
            args_slice={"count": 0},
        )
