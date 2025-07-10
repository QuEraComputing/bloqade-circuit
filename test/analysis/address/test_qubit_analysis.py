import pytest
from util import collect_address_types

from bloqade.squin import op, qubit, kernel
from bloqade.analysis import address

# test tuple and indexing


def test_tuple_address():

    @kernel
    def test():
        q1 = qubit.new(5)
        q2 = qubit.new(10)
        qubit.broadcast(op.y(), q1)
        qubit.apply(op.x(), q2[2])  # desugar creates a new ilist here
        # natural to expect two AddressTuple types
        return (q1[1], q2)

    test.print()

    address_analysis = address.AddressAnalysis(test.dialects)
    frame, _ = address_analysis.run_analysis(test, no_raise=False)
    address_types = collect_address_types(frame, address.AddressTuple)

    # should be two AddressTuples, with the last one having a structure of:
    # AddressTuple(data=(AddressQubit(1), AddressReg(data=range(5,15))))
    assert len(address_types) == 2
    assert address_types[-1].data == (
        address.AddressQubit(1),
        address.AddressReg(data=range(5, 15)),
    )


def test_get_item():

    @kernel
    def test():
        q = qubit.new(5)
        qubit.broadcast(op.y(), q)
        x = (q[0], q[3])  # -> AddressTuple(AddressQubit, AddressQubit)
        y = q[2]  # getitem on ilist # -> AddressQubit
        z = x[0]  # getitem on tuple # -> AddressQubit
        return (y, z, x)

    address_analysis = address.AddressAnalysis(test.dialects)
    frame, _ = address_analysis.run_analysis(test, no_raise=False)

    address_tuples = collect_address_types(frame, address.AddressTuple)
    address_qubits = collect_address_types(frame, address.AddressQubit)

    assert (
        address.AddressTuple(data=(address.AddressQubit(0), address.AddressQubit(3)))
        in address_tuples
    )
    assert address.AddressQubit(2) in address_qubits
    assert address.AddressQubit(0) in address_qubits


def test_invoke():

    @kernel
    def extract_qubits(qubits):
        return (qubits[1], qubits[2])

    @kernel
    def test():
        q = qubit.new(5)
        qubit.broadcast(op.y(), q)
        return extract_qubits(q)

    address_analysis = address.AddressAnalysis(test.dialects)
    frame, _ = address_analysis.run_analysis(test, no_raise=False)

    address_tuples = collect_address_types(frame, address.AddressTuple)

    assert address_tuples[-1] == address.AddressTuple(
        data=(address.AddressQubit(1), address.AddressQubit(2))
    )


@pytest.mark.xfail  # fails due to bug in for loop variable, see issue kirin#408
# Should no longer fail after upgrade to kirin 0.18 happens
def test_for_loop_idx():
    @kernel
    def main():
        q = qubit.new(3)
        x = op.x()
        for i in range(3):
            qubit.apply(x, [q[i]])

        return q

    address_analysis = address.AddressAnalysis(main.dialects)
    address_analysis.run_analysis(main, no_raise=False)
