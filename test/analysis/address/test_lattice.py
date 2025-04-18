from bloqade.analysis.address import AddressReg, AddressWire, AddressQubit


def test_address_wire_is_subset_eq():

    origin_qubit_0 = AddressQubit(data=0)
    address_wire_0 = AddressWire(origin_qubit=origin_qubit_0)

    origin_qubit_1 = AddressQubit(data=1)
    address_wire_1 = AddressWire(origin_qubit=origin_qubit_1)

    assert address_wire_0.is_subseteq(address_wire_0)
    assert not address_wire_0.is_subseteq(address_wire_1)

    # fully exercise logic with lattice type that is not address wire
    address_reg = AddressReg(data=[0, 1, 2, 3])
    assert not address_wire_0.is_subseteq(address_reg)
