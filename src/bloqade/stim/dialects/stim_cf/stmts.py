from kirin import ir
from kirin.decl import info, statement

from ._dialect import dialect


@statement(dialect=dialect)
class Repeat(ir.Statement):
    name = "REPEAT"
    traits = frozenset({ir.HasCFG(), ir.SSACFG()})
    count: int = info.attribute()
    body: ir.Region = info.region(multi=False)
