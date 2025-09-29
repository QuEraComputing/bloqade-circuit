from dataclasses import dataclass

from kirin import ir
from kirin.rewrite.abc import RewriteRule


@dataclass
class GateRule(RewriteRule):
    squin_stmt: type[ir.Statement]
    native_method: ir.Method
