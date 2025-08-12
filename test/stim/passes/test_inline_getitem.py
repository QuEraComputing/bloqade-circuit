from kirin.dialects.ilist.rewrite import InlineGetItem
from kirin.rewrite import Fixpoint
from bloqade.squin import qubit, op, kernel


@kernel
def test():
    q = qubit.new(6)
    qubit.apply(op.x(), q[2])

    ms = qubit.measure(q)
    msi = ms[1:]  # MeasureIdTuple becomes a python tuple
    msi2 = msi[1:]  # slicing should still work on previous tuple
    ms_final = msi2[::2]

    return ms_final

test.print()

Fixpoint(InlineGetItem()).rewrite(test.code)

test.print()



