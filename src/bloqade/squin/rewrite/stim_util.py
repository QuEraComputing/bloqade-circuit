from typing import cast

from kirin import ir
from kirin.dialects import py

from bloqade import stim
from bloqade.squin import op, wire, qubit
from bloqade.analysis.address import AddressWire, AddressQubit, AddressTuple
from bloqade.squin.analysis.nsites import NumberSites
from bloqade.squin.rewrite.wrap_analysis import SitesAttribute, AddressAttribute


def get_stim_1q_gate(squin_op: op.stmts.Operator):
    """
    Map squin 1Q Ops to stim Ops.
    """
    match squin_op:
        case op.stmts.X():
            return stim.gate.X
        case op.stmts.Y():
            return stim.gate.Y
        case op.stmts.Z():
            return stim.gate.Z
        case op.stmts.H():
            return stim.gate.H
        case op.stmts.S():
            return stim.gate.S
        case op.stmts.Identity():
            return stim.gate.Identity
        case _:
            raise NotImplementedError(
                f"The squin operator {squin_op} is not supported in the stim dialect"
            )


def insert_qubit_idx_from_address(
    address: AddressAttribute, stmt_to_insert_before: ir.Statement
) -> tuple[ir.SSAValue, ...]:
    """
    Extract qubit indices from an AddressAttribute and insert them into the SSA form.
    """
    address_data = address.address
    qubit_idx_ssas = []

    if isinstance(address_data, AddressTuple):
        for address_qubit in address_data.data:
            if not isinstance(address_qubit, AddressQubit):
                raise ValueError(
                    "Unsupported Address type detected inside AddressTuple, must be AddressQubit"
                )
            qubit_idx = address_qubit.data
            qubit_idx_stmt = py.Constant(qubit_idx)
            qubit_idx_stmt.insert_before(stmt_to_insert_before)
            qubit_idx_ssas.append(qubit_idx_stmt.result)
    elif isinstance(address_data, AddressWire):
        address_qubit = address_data.origin_qubit
        qubit_idx = address_qubit.data
        qubit_idx_stmt = py.Constant(qubit_idx)
        qubit_idx_stmt.insert_before(stmt_to_insert_before)
        qubit_idx_ssas.append(qubit_idx_stmt.result)
    else:
        raise NotImplementedError(
            "qubit idx extraction and insertion only supported for AddressTuple[AddressQubit] and AddressWire instances"
        )

    return tuple(qubit_idx_ssas)


def insert_qubit_idx_from_wire_ssa(
    wire_ssas: tuple[ir.SSAValue, ...], stmt_to_insert_before: ir.Statement
) -> tuple[ir.SSAValue, ...]:
    """
    Extract qubit indices from wire SSA values and insert them into the SSA form.
    """
    qubit_idx_ssas = []
    for wire_ssa in wire_ssas:
        address_attribute = wire_ssa.hints.get("address")
        assert isinstance(address_attribute, AddressAttribute)
        wire_address = address_attribute.address
        assert isinstance(wire_address, AddressWire)
        qubit_idx = wire_address.origin_qubit.data
        qubit_idx_stmt = py.Constant(qubit_idx)
        qubit_idx_ssas.append(qubit_idx_stmt.result)
        qubit_idx_stmt.insert_before(stmt_to_insert_before)

    return tuple(qubit_idx_ssas)


def verify_num_sites(stmt: wire.Apply | qubit.Apply | wire.Broadcast | qubit.Broadcast):
    """
    Verify that the number of qubits/wires matches the number of sites supported by the operator.
    """
    if isinstance(stmt, (wire.Apply, wire.Broadcast)):
        num_sites_targeted = len(stmt.inputs)
    elif isinstance(stmt, (qubit.Apply, qubit.Broadcast)):
        address_attr = stmt.qubits.hints.get("address")
        assert isinstance(address_attr, AddressAttribute)
        address_tuple = address_attr.address
        assert isinstance(address_tuple, AddressTuple)
        num_sites_targeted = len(address_tuple.data)
    else:
        raise TypeError(
            "Number of sites verification can only occur on Apply or Broadcast statements"
        )

    op_ssa = stmt.operator
    op_stmt = op_ssa.owner
    cast(ir.Statement, op_stmt)

    sites_attr = op_ssa.hints.get("sites")
    assert isinstance(sites_attr, SitesAttribute)
    sites_type = sites_attr.sites
    assert isinstance(sites_type, NumberSites)
    num_sites_supported = sites_type.sites

    if isinstance(stmt, (wire.Broadcast, qubit.Broadcast)):
        if num_sites_targeted % num_sites_supported != 0:
            raise ValueError(
                "Number of qubits/wires to broadcast to must be a multiple of the number of sites supported by the operator"
            )
    elif isinstance(stmt, (wire.Apply, qubit.Apply)):
        if num_sites_targeted != num_sites_supported:
            raise ValueError(
                "Number of qubits/wires to apply to must match the number of sites supported by the operator"
            )
