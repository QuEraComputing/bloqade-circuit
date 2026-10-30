"""Send squin kernels through jeff, optimize them there, and bring them back."""

# %%
from collections import Counter

from kirin import ir
from kirin.rewrite import Walk, Fixpoint
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.jeff import JeffToSquin, SquinToJeff, emit_jeff, load_jeff
from bloqade.types import Qubit
from bloqade.pyqrack import DynamicMemorySimulator
from bloqade.jeff.dialects.stmts import Gate


# %%
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


@squin.kernel
def ghz(n: int):
    qs = squin.qalloc(n)
    squin.h(qs[0])
    for i in range(n - 1):
        squin.cx(qs[i], qs[i + 1])
    return squin.measure(qs[0]) == squin.measure(qs[n - 1])


def gates(method: ir.Method) -> dict[str, int]:
    """Count the gates of a jeff method by name."""
    return dict(
        Counter(
            s.gate_name for s in method.callable_region.walk() if isinstance(s, Gate)
        )
    )


def equiv_result(kernel1: ir.Method, kernel2: ir.Method, shots: int = 100) -> bool:
    """Check that both kernels give the same counts for n = 2, 3 and 4."""

    def counts(kernel, n):
        return Counter(
            DynamicMemorySimulator().run(kernel, args=(n,)) for _ in range(shots)
        )

    return all(counts(kernel1, n) == counts(kernel2, n) for n in (2, 3, 4))


# %%
jeff = SquinToJeff().emit(main)
jeff.print()
print("gates:", gates(jeff))

# %%
emit_jeff(jeff).write_out("main.jeff")
jeff = load_jeff("main.jeff")
print("round trip equivalent:", equiv_result(main, JeffToSquin().emit(jeff)))

# %% ghz uses a register of dynamic size and an index loop.
emit_jeff(SquinToJeff().emit(ghz)).write_out("ghz.jeff")
print("ghz equivalent:", equiv_result(ghz, JeffToSquin().emit(load_jeff("ghz.jeff"))))


# %%
def is_h(stmt) -> bool:
    return (
        isinstance(stmt, Gate)
        and stmt.gate_name == "h"
        and not stmt.controls
        and stmt.power == 1
    )


class CancelHH(RewriteRule):
    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not is_h(node):
            return RewriteResult()
        first = node.targets[0].owner
        if not is_h(first):
            return RewriteResult()
        # Each wire has one use, so node is the only user of the output of first.
        node.results[0].replace_by(first.targets[0])
        node.delete()
        first.delete()
        return RewriteResult(has_done_something=True)


Fixpoint(Walk(CancelHH())).rewrite(jeff.code)
print("gates after CancelHH:", gates(jeff))
print("CancelHH equivalent:", equiv_result(main, JeffToSquin().emit(jeff)))

# %% This cell runs only if mqt-core is installed.
try:
    from mqt.core.mlir import JeffProgram, OutputFormat, compile_program
except ImportError:
    print("Install mqt-core to run the MQT cell.")
else:
    optimized = compile_program(
        JeffProgram.from_file("main.jeff"), output=OutputFormat.JEFF
    )
    optimized.write("mqt.jeff")
    print(
        "MQT equivalent:", equiv_result(main, JeffToSquin().emit(load_jeff("mqt.jeff")))
    )
