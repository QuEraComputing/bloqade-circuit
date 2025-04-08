"""Inline QASM dialect.

This dialect allows users to use QASM string as part of a `@qasm2.main` kernel.
"""

import ast
import textwrap
from dataclasses import dataclass

from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.print import Printer

dialect = ir.Dialect("qasm2.inline")


@dataclass(frozen=True)
class InlineQASMLowering(lowering.FromPythonCall):

    def lower(
        self, stmt: type, state: lowering.State, node: ast.Call
    ) -> lowering.Result:
        from bloqade.qasm2.parse import loads
        from bloqade.qasm2.parse.lowering import QASM2

        if len(node.args) != 1 or node.keywords:
            raise lowering.BuildError("InlineQASM takes 1 positional argument")
        text = node.args[0]
        # 1. string literal
        if isinstance(text, ast.Constant) and isinstance(text.value, str):
            value = text.value
        elif isinstance(text, ast.Name) and isinstance(text.ctx, ast.Load):
            value = state.get_global(text).expect(str)
        else:
            raise lowering.BuildError(
                "InlineQASM takes a string literal or global string"
            )

        from kirin.dialects import ilist

        from bloqade.qasm2.groups import main
        from bloqade.qasm2.dialects import glob, noise, parallel

        raw = textwrap.dedent(value)
        qasm_lowering = QASM2(main.union([ilist, glob, noise, parallel]))
        region = qasm_lowering.run(loads(raw))
        for qasm_stmt in region.blocks[0].stmts:
            qasm_stmt.detach()
            state.current_frame.push(qasm_stmt)

        for block in region.blocks:
            for qasm_stmt in block.stmts:
                qasm_stmt.detach()
                state.current_frame.push(qasm_stmt)
            state.current_frame.jump_next_block()


# NOTE: this is a dummy statement that won't appear in IR.
# TODO: maybe we should save the string in IR then rewrite?
#       what would be the use case?
@statement(dialect=dialect)
class InlineQASM(ir.Statement):
    name = "text"
    traits = frozenset({InlineQASMLowering()})
    text: str = info.attribute(types.String)

    def __init__(self, text: str) -> None:
        super().__init__(attributes={"text": ir.PyAttr(text)})

    def print_impl(self, printer: Printer) -> None:
        printer.print_name(self)
        printer.plain_print('"""')
        for line in self.text.splitlines():
            printer.plain_print(line)
            printer.print_newline()
        printer.plain_print('"""')
