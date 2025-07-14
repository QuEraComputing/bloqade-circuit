from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteResult

from bloqade.squin import op, wire, noise as squin_noise, qubit
from bloqade.squin.rewrite import AddressAttribute
from bloqade.stim.dialects import gate, noise as stim_noise, collapse
from bloqade.analysis.address import AddressReg, AddressWire, AddressQubit, AddressTuple

SQUIN_STIM_OP_MAPPING = {
    op.stmts.X: gate.X,
    op.stmts.Y: gate.Y,
    op.stmts.Z: gate.Z,
    op.stmts.H: gate.H,
    op.stmts.S: gate.S,
    op.stmts.SqrtX: gate.SqrtX,
    op.stmts.SqrtY: gate.SqrtY,
    op.stmts.Identity: gate.Identity,
    op.stmts.Reset: collapse.RZ,
    squin_noise.stmts.QubitLoss: stim_noise.QubitLoss,
}

# Squin allows creation of control gates where the gate can be any operator,
# but Stim only supports CX, CY, and CZ as control gates.
SQUIN_STIM_CONTROL_GATE_MAPPING = {
    op.stmts.X: gate.CX,
    op.stmts.Y: gate.CY,
    op.stmts.Z: gate.CZ,
}


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


def insert_qubit_idx_from_wire_ssa(
    wire_ssas: tuple[ir.SSAValue, ...], stmt_to_insert_before: ir.Statement
) -> tuple[ir.SSAValue, ...] | None:
    """
    Extract qubit indices from wire SSA values and insert them into the SSA form.
    """
    qubit_idx_ssas = []
    for wire_ssa in wire_ssas:
        address_attribute = wire_ssa.hints.get("address")
        if address_attribute is None:
            return
        assert isinstance(address_attribute, AddressAttribute)
        wire_address = address_attribute.address
        assert isinstance(wire_address, AddressWire)
        qubit_idx = wire_address.origin_qubit.data
        qubit_idx_stmt = py.Constant(qubit_idx)
        qubit_idx_ssas.append(qubit_idx_stmt.result)
        qubit_idx_stmt.insert_before(stmt_to_insert_before)

    return tuple(qubit_idx_ssas)


def insert_qubit_idx_after_apply(
    stmt: wire.Apply | qubit.Apply | wire.Broadcast | qubit.Broadcast,
) -> tuple[ir.SSAValue, ...] | None:
    """
    Extract qubit indices from Apply or Broadcast statements.
    """
    if isinstance(stmt, (qubit.Apply, qubit.Broadcast)):
        qubits = stmt.qubits
        address_attribute = qubits.hints.get("address")
        if address_attribute is None:
            return
        assert isinstance(address_attribute, AddressAttribute)
        return insert_qubit_idx_from_address(
            address=address_attribute, stmt_to_insert_before=stmt
        )
    elif isinstance(stmt, (wire.Apply, wire.Broadcast)):
        wire_ssas = stmt.inputs
        return insert_qubit_idx_from_wire_ssa(
            wire_ssas=wire_ssas, stmt_to_insert_before=stmt
        )


def rewrite_Control(
    stmt_with_ctrl: qubit.Apply | wire.Apply | qubit.Broadcast | wire.Broadcast,
) -> RewriteResult:
    """
    Handle control gates for Apply and Broadcast statements.
    """
    ctrl_op = stmt_with_ctrl.operator.owner
    assert isinstance(ctrl_op, op.stmts.Control)

    ctrl_op_target_gate = ctrl_op.op.owner
    assert isinstance(ctrl_op_target_gate, op.stmts.Operator)

    qubit_idx_ssas = insert_qubit_idx_after_apply(stmt=stmt_with_ctrl)
    if qubit_idx_ssas is None:
        return RewriteResult()

    # Separate control and target qubits
    target_qubits = []
    ctrl_qubits = []
    for i in range(len(qubit_idx_ssas)):
        if (i % 2) == 0:
            ctrl_qubits.append(qubit_idx_ssas[i])
        else:
            target_qubits.append(qubit_idx_ssas[i])

    target_qubits = tuple(target_qubits)
    ctrl_qubits = tuple(ctrl_qubits)

    stim_gate = SQUIN_STIM_CONTROL_GATE_MAPPING.get(type(ctrl_op_target_gate))
    if stim_gate is None:
        return RewriteResult()

    stim_stmt = stim_gate(controls=ctrl_qubits, targets=target_qubits)

    if isinstance(stmt_with_ctrl, (wire.Apply, wire.Broadcast)):
        create_wire_passthrough(stmt_with_ctrl)

    stmt_with_ctrl.replace_by(stim_stmt)

    return RewriteResult(has_done_something=True)


def rewrite_QubitLoss(
    stmt: qubit.Apply | qubit.Broadcast | wire.Broadcast | wire.Apply,
) -> RewriteResult:
    """
    Rewrite QubitLoss statements to Stim's TrivialError.
    """

    squin_loss_op = stmt.operator.owner
    assert isinstance(squin_loss_op, squin_noise.stmts.QubitLoss)

    qubit_idx_ssas = insert_qubit_idx_after_apply(stmt=stmt)
    if qubit_idx_ssas is None:
        return RewriteResult()

    stim_loss_stmt = stim_noise.QubitLoss(
        targets=qubit_idx_ssas,
        probs=(squin_loss_op.p,),
    )

    if isinstance(stmt, (wire.Apply, wire.Broadcast)):
        create_wire_passthrough(stmt)

    stmt.replace_by(stim_loss_stmt)

    return RewriteResult(has_done_something=True)


def create_wire_passthrough(stmt: wire.Apply | wire.Broadcast) -> None:

    for input_wire, output_wire in zip(stmt.inputs, stmt.results):
        # have to "reroute" the input of these statements to directly plug in
        # to subsequent statements, remove dependency on the current statement
        output_wire.replace_by(input_wire)


def is_measure_result_used(
    stmt: qubit.MeasureQubit | qubit.MeasureQubitList | wire.Measure,
) -> bool:
    """
    Check if the result of a measure statement is used in the program.
    """
    return bool(stmt.result.uses)
