from kirin import ir, types
from kirin.dialects import func, ilist
from kirin.dialects.py import constant

from bloqade import qasm2
from bloqade.analysis import address
from bloqade.test_utils import assert_nodes
from bloqade.qasm2.dialects import uop, core, glob, noise, parallel
from bloqade.qasm2.passes.noise import NoisePass
from bloqade.qasm2.rewrite.noise.heuristic_noise import NoiseRewriteRule


class NoiseTestModel(noise.MoveNoiseModelABC):
    def parallel_cz_errors(self, ctrls, qargs, rest):
        return {(0.01, 0.01, 0.01, 0.01): ctrls + qargs + rest}


def test_single_qubit_noise():
    px = 0.01
    py = 0.01
    pz = 0.01
    p_loss = 0.01

    model = NoiseTestModel(
        local_px=px, local_py=py, local_pz=pz, local_loss_prob=p_loss
    )

    test_qubit = ir.TestValue(type=qasm2.QubitType)
    address_analysis = {test_qubit: address.AddressQubit(0)}
    qubit_ssa_value = {0: test_qubit}
    rule = NoiseRewriteRule(address_analysis, qubit_ssa_value, model)
    rule.qubit_ssa_value[0] = test_qubit
    block = ir.Block(
        [
            stmt := uop.X(qarg=test_qubit),
        ]
    )

    rule.rewrite(stmt)

    expected_block = ir.Block(
        [
            qubit_list := ilist.New(values=[test_qubit]),
            noise.PauliChannel(qargs=qubit_list.result, px=px, py=py, pz=pz),
            noise.AtomLossChannel(qargs=qubit_list.result, prob=p_loss),
            stmt.from_stmt(stmt),
        ]
    )

    assert_nodes(block, expected_block)


def test_parallel_qubit_noise():
    px = 0.01
    py = 0.01
    pz = 0.01
    p_loss = 0.01

    model = NoiseTestModel(
        local_px=px, local_py=py, local_pz=pz, local_loss_prob=p_loss
    )

    test_qubit = ir.TestValue(type=qasm2.QubitType)
    qubit_list = ilist.New(values=[test_qubit])

    test_float = ir.TestValue(type=types.Float)
    address_analysis = {
        test_qubit: address.AddressQubit,
        qubit_list.result: address.AddressTuple([address.AddressQubit(0)]),
    }
    qubit_ssa_value = {0: test_qubit}

    rule = NoiseRewriteRule(address_analysis, qubit_ssa_value, model)
    rule.qubit_ssa_value[0] = test_qubit
    block = ir.Block(
        [
            qubit_list,
            stmt := parallel.UGate(
                qargs=qubit_list.result,
                theta=test_float,
                phi=test_float,
                lam=test_float,
            ),
        ]
    )

    rule.rewrite(stmt)

    expected_block = ir.Block(
        [
            qubit_list := qubit_list.from_stmt(qubit_list),
            noise.PauliChannel(qargs=qubit_list.result, px=px, py=py, pz=pz),
            noise.AtomLossChannel(qargs=qubit_list.result, prob=p_loss),
            parallel.UGate(
                qargs=qubit_list.result,
                theta=test_float,
                phi=test_float,
                lam=test_float,
            ),
        ]
    )

    assert_nodes(block, expected_block)


def test_cz_gate_noise():
    px = 0.01
    py = 0.01
    pz = 0.01
    p_loss = 0.01

    model = NoiseTestModel(
        cz_paired_gate_px=px,
        cz_paired_gate_py=py,
        cz_paired_gate_pz=pz,
        cz_gate_loss_prob=p_loss,
        cz_unpaired_gate_px=px,
        cz_unpaired_gate_py=py,
        cz_unpaired_gate_pz=pz,
        cz_unpaired_loss_prob=p_loss,
    )

    ctrl_qubit = ir.TestValue(type=qasm2.QubitType)
    qarg_qubit = ir.TestValue(type=qasm2.QubitType)
    address_analysis = {
        ctrl_qubit: address.AddressQubit(0),
        qarg_qubit: address.AddressQubit(1),
    }
    qubit_ssa_value = {0: ctrl_qubit, 1: qarg_qubit}
    rule = NoiseRewriteRule(address_analysis, qubit_ssa_value, model)
    rule.qubit_ssa_value[0] = ctrl_qubit
    rule.qubit_ssa_value[1] = qarg_qubit
    block = ir.Block(
        [
            stmt := uop.CZ(qarg=qarg_qubit, ctrl=ctrl_qubit),
        ]
    )

    rule.rewrite(stmt)

    expected_block = ir.Block(
        [
            ctrls := ilist.New(values=[ctrl_qubit]),
            qargs := ilist.New(values=[qarg_qubit]),
            all_qubits := ilist.New(values=[ctrl_qubit, qarg_qubit]),
            noise.AtomLossChannel(qargs=all_qubits.result, prob=p_loss),
            noise.PauliChannel(qargs=all_qubits.result, px=px, py=py, pz=pz),
            noise.CZPauliChannel(
                ctrls=ctrls.result,
                qargs=qargs.result,
                px_ctrl=px,
                py_ctrl=py,
                pz_ctrl=pz,
                px_qarg=px,
                py_qarg=py,
                pz_qarg=pz,
                paired=True,
            ),
            noise.CZPauliChannel(
                ctrls=ctrls.result,
                qargs=qargs.result,
                px_ctrl=px,
                py_ctrl=py,
                pz_ctrl=pz,
                px_qarg=px,
                py_qarg=py,
                pz_qarg=pz,
                paired=False,
            ),
            noise.AtomLossChannel(qargs=ctrls.result, prob=p_loss),
            noise.AtomLossChannel(qargs=qargs.result, prob=p_loss),
            stmt.from_stmt(stmt),
        ]
    )

    assert_nodes(block, expected_block)


def test_parallel_cz_gate_noise():
    px = 0.01
    py = 0.01
    pz = 0.01
    p_loss = 0.01

    model = NoiseTestModel(
        cz_paired_gate_px=px,
        cz_paired_gate_py=py,
        cz_paired_gate_pz=pz,
        cz_gate_loss_prob=p_loss,
        cz_unpaired_gate_px=px,
        cz_unpaired_gate_py=py,
        cz_unpaired_gate_pz=pz,
        cz_unpaired_loss_prob=p_loss,
    )

    ctrl_qubit = ir.TestValue(type=qasm2.QubitType)
    qarg_qubit = ir.TestValue(type=qasm2.QubitType)
    ctrl_list = ilist.New(values=[ctrl_qubit])
    qarg_list = ilist.New(values=[qarg_qubit])
    address_analysis = {
        ctrl_qubit: address.AddressQubit(0),
        qarg_qubit: address.AddressQubit(1),
        ctrl_list.result: address.AddressTuple([address.AddressQubit(0)]),
        qarg_list.result: address.AddressTuple([address.AddressQubit(1)]),
    }
    qubit_ssa_value = {0: ctrl_qubit, 1: qarg_qubit}
    rule = NoiseRewriteRule(address_analysis, qubit_ssa_value, model)
    rule.qubit_ssa_value[0] = ctrl_qubit
    rule.qubit_ssa_value[1] = qarg_qubit
    block = ir.Block(
        [
            ctrl_list,
            qarg_list,
            stmt := parallel.CZ(qargs=qarg_list.result, ctrls=ctrl_list.result),
        ]
    )

    rule.rewrite(stmt)

    expected_block = ir.Block(
        [
            ctrl_list := ctrl_list.from_stmt(ctrl_list),
            qarg_list := qarg_list.from_stmt(qarg_list),
            all_qubits := ilist.New(values=[ctrl_qubit, qarg_qubit]),
            noise.AtomLossChannel(qargs=all_qubits.result, prob=p_loss),
            noise.PauliChannel(qargs=all_qubits.result, px=px, py=py, pz=pz),
            noise.CZPauliChannel(
                ctrls=ctrl_list.result,
                qargs=qarg_list.result,
                px_ctrl=px,
                py_ctrl=py,
                pz_ctrl=pz,
                px_qarg=px,
                py_qarg=py,
                pz_qarg=pz,
                paired=True,
            ),
            noise.CZPauliChannel(
                ctrls=ctrl_list.result,
                qargs=qarg_list.result,
                px_ctrl=px,
                py_ctrl=py,
                pz_ctrl=pz,
                px_qarg=px,
                py_qarg=py,
                pz_qarg=pz,
                paired=False,
            ),
            noise.AtomLossChannel(qargs=ctrl_list.result, prob=p_loss),
            noise.AtomLossChannel(qargs=qarg_list.result, prob=p_loss),
            parallel.CZ(qargs=qarg_list.result, ctrls=ctrl_list.result),
        ]
    )

    assert_nodes(block, expected_block)


def test_global_noise():

    @qasm2.extended
    def test_method():
        q0 = qasm2.qreg(1)
        q1 = qasm2.qreg(1)
        qasm2.glob.u([q0, q1], 0.1, 0.2, 0.3)

    px = 0.01
    py = 0.01
    pz = 0.01
    p_loss = 0.01

    model = NoiseTestModel(
        global_loss_prob=p_loss, global_px=px, global_py=py, global_pz=pz
    )

    test_method.print()

    NoisePass(test_method.dialects, noise_model=model)(test_method)

    expected_block = ir.Block(
        [
            n_qubits := constant.Constant(1),
            reg1 := core.QRegNew(n_qubits.result),
            zero := constant.Constant(0),
            q1 := core.QRegGet(reg1.result, zero.result),
            reg0 := core.QRegNew(n_qubits.result),
            q0 := core.QRegGet(reg0.result, zero.result),
            reg_list := ilist.New(
                values=[reg0.result, reg1.result], elem_type=reg0.result.type
            ),
            theta := constant.Constant(0.1),
            phi := constant.Constant(0.2),
            lam := constant.Constant(0.3),
            qargs := ilist.New(values=[q0.result, q1.result]),
            noise.PauliChannel(qargs.result, px=px, py=py, pz=pz),
            noise.AtomLossChannel(qargs.result, prob=p_loss),
            glob.UGate(reg_list.result, theta.result, phi.result, lam.result),
            none := func.ConstantNone(),
            func.Return(none.result),
        ],
        argtypes=[types.MethodType[[], types.NoneType]],
    )

    expected_block.args[0].name = "test_method_self"

    reg0.result.name = "q0"
    reg1.result.name = "q1"
    expected_region = ir.Region([expected_block])
    assert_nodes(test_method.callable_region, expected_region)
