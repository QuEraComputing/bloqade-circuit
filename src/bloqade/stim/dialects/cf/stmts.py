from typing import cast

from kirin import ir, types
from kirin.decl import info, statement

from ._dialect import dialect


@statement(dialect=dialect, init=False)
class REPEAT(ir.Statement):
    """Repeat statement for looping a fixed number of times.

    This statement has a loop count and a body.
    """

    name = "REPEAT"
    count: ir.SSAValue = info.argument(types.Int)
    body: ir.Region = info.region(multi=False)

    def __init__(
        self,
        count: ir.SSAValue,
        body: ir.Region | ir.Block,
    ):
        if body.IS_REGION:
            body_region = cast(ir.Region, body)
            if body_region.blocks:
                body_block = body_region.blocks[0]
            else:
                body_block = None
        else:
            body_block = cast(ir.Block, body)
            body_region = ir.Region(body_block)

        super().__init__(args=(count,), regions=(body_region,), args_slice={"count": 0})
