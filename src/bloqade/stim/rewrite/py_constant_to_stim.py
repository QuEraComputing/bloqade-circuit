from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.stim.dialects import auxiliary

# py.constant.int -> stim.const.ConstInt
# py.constant.float -> stimt.const.ConstFloat
# py.constant -> stim.const.ConstBool
#


class PyConstantToStim(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case py.constant.Constant():
                return self.rewrite_PyConstant(node)
            case _:
                return RewriteResult()

    def rewrite_PyConstant(self, node: py.constant.Constant) -> RewriteResult:

        # node.value is a PyAttr, need to get the
        # wrapped value out
        wrapped_value = node.value.unwrap()

        if isinstance(wrapped_value, int):
            stim_const = auxiliary.ConstInt(value=wrapped_value)
        elif isinstance(wrapped_value, float):
            stim_const = auxiliary.ConstFloat(value=wrapped_value)
        elif isinstance(wrapped_value, bool):
            stim_const = auxiliary.ConstBool(value=wrapped_value)
        elif isinstance(wrapped_value, str):
            stim_const = auxiliary.ConstStr(value=wrapped_value)
        else:
            return RewriteResult()

        node.replace_by(stim_const)

        return RewriteResult(has_done_something=True)
