from kirin import ir
from kirin.dialects import py

from bloqade.analysis.address import Address, AddressReg, AddressQubit


def create_and_insert_qubit_idx_stmt(
    qubit_idx, stmt_to_insert_before: ir.Statement, qubit_idx_ssas: list
):
    qubit_idx_stmt = py.Constant(qubit_idx)
    qubit_idx_stmt.insert_before(stmt_to_insert_before)
    qubit_idx_ssas.append(qubit_idx_stmt.result)


def insert_qubit_idx_from_address(
    address: Address, stmt_to_insert_before: ir.Statement
) -> tuple[ir.SSAValue, ...] | None:
    """
    Extract qubit indices from an address analysis lattice element and insert them into the SSA form.
    """
    qubit_idx_ssas = []
    if isinstance(address, AddressReg):
        for qubit_idx in address.qubits:
            create_and_insert_qubit_idx_stmt(
                qubit_idx.data, stmt_to_insert_before, qubit_idx_ssas
            )
    elif isinstance(address, AddressQubit):
        create_and_insert_qubit_idx_stmt(
            address.data, stmt_to_insert_before, qubit_idx_ssas
        )
    else:
        return

    return tuple(qubit_idx_ssas)
