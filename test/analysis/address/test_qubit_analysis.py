import pytest
from util import collect_address_types
from kirin.analysis import const
from kirin.dialects import scf, ilist

from bloqade import qubit, squin
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
    frame, _ = address_analysis.run(test)
    address_types = collect_address_types(frame, address.PartialTuple)

    test.print(analysis=frame.entries)

    # should be two AddressTuples, with the last one having a structure of:
    # AddressTuple(data=(AddressQubit(1), AddressReg(data=range(5,15))))
    assert len(address_types) == 1
    assert address_types[0].data == (
        address.AddressQubit(1),
        address.AddressReg(data=tuple(range(5, 15))),
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
    frame, _ = address_analysis.run(test)

    address_tuples = collect_address_types(frame, address.PartialTuple)
    address_qubits = collect_address_types(frame, address.AddressQubit)

    assert (
        address.PartialTuple(data=(address.AddressQubit(0), address.AddressQubit(3)))
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
    frame, _ = address_analysis.run(test)

    address_tuples = collect_address_types(frame, address.PartialTuple)

    assert address_tuples[-1] == address.PartialTuple(
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
    frame, _ = address_analysis.run(main)

    address_regs = collect_address_types(frame, address.AddressReg)
    address_qubits = collect_address_types(frame, address.AddressQubit)

    assert address_regs[0] == address.AddressReg(data=tuple(range(0, 4)))
    assert address_regs[1] == address.AddressReg(data=tuple(range(1, 3)))

    assert address_qubits[0] == address.AddressQubit(data=1)


def test_for_loop_idx():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        for i in range(3):
            squin.x(q[i])

        return q

    address_analysis = address.AddressAnalysis(main.dialects)
    address_analysis.run(main)


def test_new_qubit():
    @squin.kernel
    def main():
        return squin.qubit.new()

    address_analysis = address.AddressAnalysis(main.dialects)
    _, result = address_analysis.run(main)
    assert result == address.AddressQubit(0)


def test_partial_tuple_constant():
    @squin.kernel
    def main(n: int):
        qreg = []
        for _ in (0, 1, 2, n):
            qreg = qreg + [squin.qubit.new()]

        return qreg

    address_analysis = address.AddressAnalysis(main.dialects)
    frame, result = address_analysis.run(
        main,
        address.ConstResult(const.Unknown()),
    )
    assert result == address.AddressReg(data=tuple(range(4)))


def test_partial_tuple():
    @squin.kernel
    def main(n: int):
        qreg = []
        for _ in (0, 1, 2, n):
            qreg = qreg + [squin.qubit.new()]

        return qreg

    address_analysis = address.AddressAnalysis(main.dialects)
    frame, result = address_analysis.run(main)
    assert result == address.AddressReg(data=tuple(range(4)))


def test_partial_tuple_add():
    @squin.kernel
    def main(n: int):
        return (0, 1) + (2, n)

    address_analysis = address.AddressAnalysis(main.dialects)
    frame, result = address_analysis.run(main)

    assert result == address.PartialTuple(
        data=(
            address.ConstResult(const.Value(0)),
            address.ConstResult(const.Value(1)),
            address.ConstResult(const.Value(2)),
            address.Unknown(),
        )
    )


def test_partial_tuple_add_failed():
    @squin.kernel
    def main(n: int):
        return (0, 1) + [2, n]  # type: ignore

    address_analysis = address.AddressAnalysis(main.dialects)
    frame, result = address_analysis.run(main)

    assert result == address.Bottom()


def test_partial_tuple_add_failed_2():
    @squin.kernel
    def main(n: tuple[int, ...]):
        return (0, 1) + n

    address_analysis = address.AddressAnalysis(main.dialects)
    frame, result = address_analysis.run(main)

    assert result == address.Unknown()


# need to pass in values from argument types
@pytest.mark.xfail
def test_partial_tuple_slice():
    @squin.kernel
    def main(q: qubit.Qubit):
        return (0, q, 2, q)[1::2]

    address_analysis = address.AddressAnalysis(main.dialects)
    frame, result = address_analysis.run(main)
    assert result == address.UnknownReg()


@pytest.mark.xfail
def test_new_stdlib():
    @squin.kernel(typeinfer=True)
    def main(n: int):
        return squin.qalloc(n)

    main.print()
    address_analysis = address.AddressAnalysis(main.dialects)
    frame, result = address_analysis.run(main)
    main.print(analysis=frame.entries)
    assert (
        result == address.UnknownReg()
    )  # TODO: should be AddressTuple with AddressQubits


def test_complex_allocation():

    @squin.kernel
    def ghz_factory(size: int):
        def factory():
            q0 = squin.qubit.new()
            squin.h(q0)
            reg = ilist.IList([q0])
            for i in range(size):
                current = len(reg)
                missing = size - current
                if missing > current:
                    num_alloc = current
                else:
                    num_alloc = missing

                if num_alloc > 0:
                    new_qubits = squin.qalloc(num_alloc)
                    num_to_cx = len(new_qubits)
                    squin.broadcast.cx(reg[:num_to_cx], new_qubits)
                    reg = reg + new_qubits

            return reg

        return factory

    @squin.kernel(typeinfer=True, fold=True)
    def main():
        size = 10
        factory = ghz_factory(size)
        return factory() + factory()

    func = main
    analysis = address.AddressAnalysis(squin.kernel)
    _, ret = analysis.run(func)

    assert ret == address.AddressReg(data=tuple(range(20)))
    assert analysis.qubit_count == 20


def test_for_loop_body_values():
    @squin.kernel
    def main():
        q = squin.qalloc(4)
        for i in range(1, len(q)):
            squin.cx(q[0], q[i])

    address_analysis = address.AddressAnalysis(main.dialects)
    frame, result = address_analysis.run(main)
    main.print(analysis=frame.entries)

    (for_stmt,) = tuple(
        stmt for stmt in main.callable_region.walk() if isinstance(stmt, scf.For)
    )

    for_analysis = [
        value
        for stmt in for_stmt.body.walk()
        for value in frame.get_values(stmt.results)
    ]

    assert address.AddressQubit(data=0) in for_analysis
    assert address.ConstResult(const.Value(0)) in for_analysis
    assert address.ConstResult(const.Value(None)) in for_analysis
    assert address.Unknown() in for_analysis
