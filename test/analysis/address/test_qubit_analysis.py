import pytest
from util import collect_address_types

from bloqade import squin
from bloqade.analysis import address

# test tuple and indexing


def test_tuple_address():

    @squin.kernel
    def test():
        q1 = squin.qalloc(5)
        q2 = squin.qalloc(10)
        squin.broadcast.y(q1)
        squin.x(q2[2])  # desugar creates a new ilist here
        # natural to expect two AddressTuple types
        return (q1[1], q2)

    address_analysis = address.AddressAnalysis(test.dialects)
    frame, _ = address_analysis.run_analysis(test, no_raise=False)
    address_types = collect_address_types(frame, address.AddressTuple)

    test.print(analysis=frame.entries)

    # should be two AddressTuples, with the last one having a structure of:
    # AddressTuple(data=(AddressQubit(1), AddressReg(data=range(5,15))))
    assert len(address_types) == 1
    assert address_types[0].data == (
        address.AddressQubit(1),
        address.AddressReg(data=range(5, 15)),
    )


def test_get_item():

    @squin.kernel
    def test():
        q = squin.qalloc(5)
        squin.broadcast.y(q)
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

    @squin.kernel
    def extract_qubits(qubits):
        return (qubits[1], qubits[2])

    @squin.kernel
    def test():
        q = squin.qalloc(5)
        squin.broadcast.y(q)
        return extract_qubits(q)

    address_analysis = address.AddressAnalysis(test.dialects)
    frame, _ = address_analysis.run_analysis(test, no_raise=False)

    address_tuples = collect_address_types(frame, address.AddressTuple)

    assert address_tuples[-1] == address.AddressTuple(
        data=(address.AddressQubit(1), address.AddressQubit(2))
    )


def test_slice():

    @squin.kernel
    def main():
        q = squin.qalloc(4)
        # get the middle qubits out and apply to them
        sub_q = q[1:3]
        squin.broadcast.x(sub_q)
        # get a single qubit out, do some stuff
        single_q = sub_q[0]
        squin.h(single_q)

    address_analysis = address.AddressAnalysis(main.dialects)
    frame, _ = address_analysis.run_analysis(main, no_raise=False)

    address_regs = [
        address_reg_type
        for address_reg_type in frame.entries.values()
        if isinstance(address_reg_type, address.AddressReg)
    ]
    address_qubits = [
        address_qubit_type
        for address_qubit_type in frame.entries.values()
        if isinstance(address_qubit_type, address.AddressQubit)
    ]

    assert address_regs[0] == address.AddressReg(data=range(0, 4))
    assert address_regs[1] == address.AddressReg(data=range(1, 3))

    assert address_qubits[0] == address.AddressQubit(data=1)


def test_for_loop_idx():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        for i in range(3):
            squin.x(q[i])

        return q

    address_analysis = address.AddressAnalysis(main.dialects)
    address_analysis.run_analysis(main, no_raise=False)


def test_new_qubit():
    @squin.kernel
    def main():
        return squin.qubit.new()

    address_analysis = address.AddressAnalysis(main.dialects)
    _, result = address_analysis.run_analysis(main, no_raise=False)
    assert result == address.AddressQubit(0)


@pytest.mark.xfail  # fails due to ilist.map not being handled correctly
def test_new_stdlib():
    @squin.kernel
    def main():
        return squin.qalloc(10)

    address_analysis = address.AddressAnalysis(main.dialects)
    _, result = address_analysis.run_analysis(main, no_raise=False)
    assert (
        result == address.AnyAddress()
    )  # TODO: should be AddressTuple with AddressQubits
