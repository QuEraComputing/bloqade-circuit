"""Send a squin kernel through jeff, optimize it there, and bring it back to squin.

Run the `# %%` cells one by one in an editor that supports them, or run the
file. If `mqt-core` is installed, the last cells also optimize the kernel with
MQT Core through a jeff file.
"""

# %% The cells below import kirin, the jeff converters and a simulator.
from collections import Counter

from kirin import ir
from kirin.rewrite import Walk, Fixpoint
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.jeff import JeffToSquin, SquinToJeff, emit_jeff, load_jeff
from bloqade.types import Qubit
from bloqade.pyqrack import DynamicMemorySimulator
from bloqade.jeff.dialects.stmts import Gate


# %% A kernel with a loop: every shot measures n mod 2, because b is 1.
@squin.kernel
def flip(q: Qubit) -> None:
    squin.x(q)


@squin.kernel
def main(n: int):
    a = squin.qubit.new()
    b = squin.qubit.new()
    flip(b)
    for _ in range(n):
        squin.h(a)
        squin.h(a)
        squin.rz(0.3, a)
        squin.rz(0.2, a)
        squin.cx(b, a)
    return squin.measure(a)


def gates(method: ir.Method) -> dict[str, int]:
    """Count the gates of a jeff method by name, also inside the loop body."""
    names = Counter(
        stmt.gate_name
        for stmt in method.callable_region.walk()
        if isinstance(stmt, Gate)
    )
    return dict(names)


def counts(kernel: ir.Method) -> dict[int, dict[int, int]]:
    """Run `kernel` for 100 shots with n = 2 and n = 3, and count the bits."""
    return {
        n: dict(
            Counter(
                int(DynamicMemorySimulator().run(kernel, args=(n,))) for _ in range(100)
            )
        )
        for n in (2, 3)
    }


# %% squin to jeff: each qubit becomes a wire, and the loop stays a loop.
jeff = SquinToJeff().emit(main)
jeff.print()
print("gates:", gates(jeff))

# %% The jeff IR goes to a .jeff file and comes back.
emit_jeff(jeff).write_out("main.jeff")
jeff = load_jeff("main.jeff")


# %% A rewrite on wires: an H that follows an H on the same wire cancels it.
def is_h(stmt) -> bool:
    """Check that `stmt` is a plain H gate."""
    return (
        isinstance(stmt, Gate)
        and stmt.gate_name == "h"
        and not stmt.controls
        and stmt.power == 1
    )


class CancelHH(RewriteRule):
    """Remove two H gates in a row on one wire."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not is_h(node):
            return RewriteResult()
        first = node.targets[0].owner
        if not is_h(first):
            return RewriteResult()
        # jeff uses each wire exactly once. So node is the only user of the
        # output wire of `first`, and removing both gates is safe.
        node.results[0].replace_by(first.targets[0])
        node.delete()
        first.delete()
        return RewriteResult(has_done_something=True)


Fixpoint(Walk(CancelHH())).rewrite(jeff.code)
print("gates after CancelHH:", gates(jeff))

# %% jeff to squin: both kernels give the same counts.
back = JeffToSquin().emit(jeff)
back.print()
print("squin:          ", counts(main))
print("after CancelHH: ", counts(back))

# %% MQT Core reads the .jeff file, runs its default pipeline and writes jeff back.
try:
    from mqt.core.mlir import JeffProgram, OutputFormat, compile_program
except ImportError:
    print("Install mqt-core to run the MQT cells.")
else:
    program = JeffProgram.from_file("main.jeff")
    optimized = compile_program(program, output=OutputFormat.JEFF)
    optimized.write("mqt.jeff")
    print("before MQT:", program.operation_counts())
    print("after MQT: ", optimized.operation_counts())
    mqt = JeffToSquin().emit(load_jeff("mqt.jeff"))
    print("after MQT:      ", counts(mqt))
