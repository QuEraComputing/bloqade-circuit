from typing import TypeVar

from kirin import ir, interp
from kirin.analysis import const
from kirin.dialects import py

from bloqade.squin import wire, qubit
from bloqade.squin.rewrite import AddressAttribute
from bloqade.analysis.address import AddressReg, AddressWire, AddressQubit, AddressTuple


def create_and_insert_qubit_idx_stmt(
    qubit_idx, stmt_to_insert_before: ir.Statement, qubit_idx_ssas: list
):
    qubit_idx_stmt = py.Constant(qubit_idx)
    qubit_idx_stmt.insert_before(stmt_to_insert_before)
    qubit_idx_ssas.append(qubit_idx_stmt.result)


def insert_qubit_idx_from_address(
    address: AddressAttribute, stmt_to_insert_before: ir.Statement
) -> tuple[ir.SSAValue, ...] | None:
    """
    Extract qubit indices from an AddressAttribute and insert them into the SSA form.
    """
    address_data = address.address
    qubit_idx_ssas = []

    if isinstance(address_data, AddressTuple):
        for address_qubit in address_data.data:
            if not isinstance(address_qubit, AddressQubit):
                return
            create_and_insert_qubit_idx_stmt(
                address_qubit.data, stmt_to_insert_before, qubit_idx_ssas
            )
    elif isinstance(address_data, AddressReg):
        for qubit_idx in address_data.data:
            create_and_insert_qubit_idx_stmt(
                qubit_idx, stmt_to_insert_before, qubit_idx_ssas
            )
    elif isinstance(address_data, AddressQubit):
        create_and_insert_qubit_idx_stmt(
            address_data.data, stmt_to_insert_before, qubit_idx_ssas
        )
    elif isinstance(address_data, AddressWire):
        address_qubit = address_data.origin_qubit
        create_and_insert_qubit_idx_stmt(
            address_qubit.data, stmt_to_insert_before, qubit_idx_ssas
        )
    else:
        return

    return tuple(qubit_idx_ssas)


def is_measure_result_used(
    stmt: qubit.MeasureQubit | qubit.MeasureQubitList | wire.Measure,
) -> bool:
    """
    Check if the result of a measure statement is used in the program.
    """
    return bool(stmt.result.uses)


T = TypeVar("T")


def get_const_value(typ: type[T], value: ir.SSAValue) -> T:
    if isinstance(hint := value.hints.get("const"), const.Value):
        data = hint.data
        if isinstance(data, typ):
            return hint.data
        raise interp.InterpreterError(
            f"Expected constant value <type = {typ}>, got {data}"
        )
    raise interp.InterpreterError(
        f"Expected constant value <type = {typ}>, got {value}"
    )
