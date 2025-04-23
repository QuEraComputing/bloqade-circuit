from typing import Literal
import textwrap
from unittest.mock import Mock

import pytest
from kirin import ir
from kirin.dialects import ilist

from bloqade import qasm2
from bloqade.noise import native
from bloqade.pyqrack import PyQrackQubit, PyQrackInterpreter, reg
from bloqade.pyqrack.base import MockMemory
from bloqade.qasm2.passes import QASM2Py, NoisePass, QASM2Fold
from bloqade.qasm2.parse.lowering import QASM2

simulation = qasm2.extended.add(native)


def run_mock(program: ir.Method, rng_state: Mock | None = None):
    PyQrackInterpreter(
        program.dialects, memory=(memory := MockMemory()), rng_state=rng_state
    ).run(program, ())
    assert isinstance(mock := memory.sim_reg, Mock)
    return mock


def test_atom_loss():

    @simulation
    def test_atom_loss(c: qasm2.CReg):
        q = qasm2.qreg(2)
        native.atom_loss_channel([q[0]], prob=0.1)
        native.atom_loss_channel([q[1]], prob=0.05)
        qasm2.measure(q[0], c[0])

        return q

    rng_state = Mock()
    rng_state.uniform.return_value = 0.1
    input = reg.CRegister(1)
    memory = MockMemory()

    result: ilist.IList[PyQrackQubit, Literal[2]] = PyQrackInterpreter(
        simulation, memory=memory, rng_state=rng_state
    ).run(test_atom_loss, (input,))

    assert result[0].state is reg.QubitState.Lost
    assert result[1].state is reg.QubitState.Active
    assert input[0] is reg.Measurement.One


@pytest.mark.xfail
def test_noise_probs():
    test_qasm = textwrap.dedent(
        """
    OPENQASM 2.0;
    include "qelib1.inc";

    // Qubits: [q_0, q_1, q_2, q_3, q_4, q_5]
    qreg q[6];


    u3(pi*0.9999896015,pi*1.8867094803,pi*0.1132905197) q[2];
    u3(pi*1.499959526,pi*1.2634437582,pi*0.7365562418) q[3];
    u3(pi*1.4998447568,pi*1.8205928898,pi*0.1794071102) q[4];
    u3(pi*1.4998052589,pi*1.5780611154,pi*0.4219388846) q[5];
    u3(pi*0.4920440401,pi*1.287644074,pi*0.712355926) q[0];
    u3(pi*1.0012473155,pi*1.3019213156,pi*0.6980786844) q[1];
    cz q[1],q[2];
    cz q[1],q[2];
    cz q[2],q[3];
    cz q[4],q[5];
    cz q[2],q[3];
    cz q[4],q[5];
    cz q[2],q[3];
    cz q[4],q[5];
    cz q[2],q[3];
    cz q[4],q[5];
    cz q[2],q[3];
    cz q[4],q[5];
    u3(pi*1.0,pi*1.5687764466,pi*0.4312235534) q[2];
    u3(pi*0.5,0,pi*1.7365086077) q[3];
    u3(pi*0.5,pi*1.0,pi*0.6112880576) q[4];
    u3(pi*0.1388474164,pi*1.7687898606,pi*1.2425564668) q[5];
    """
    )

    entry = QASM2(qasm2.main.add(qasm2.inline_)).loads(test_qasm, "entry", returns="q")
    QASM2Py(entry.dialects)(entry)
    entry = entry.similar(qasm2.extended.add(native))
    QASM2Fold(entry.dialects).fixpoint(entry)

    # Noise parameters
    gate_noise_value = 1e-3
    move_noise_value = 0.5

    gate_noise_params = native.GateNoiseParams(
        local_px=gate_noise_value,
        local_py=gate_noise_value,
        local_pz=gate_noise_value,
        local_loss_prob=gate_noise_value,
        #
        global_px=gate_noise_value,
        global_py=gate_noise_value,
        global_pz=gate_noise_value,
        global_loss_prob=gate_noise_value,
        #
        cz_paired_gate_px=gate_noise_value,
        cz_paired_gate_py=gate_noise_value,
        cz_paired_gate_pz=gate_noise_value,
        cz_gate_loss_prob=gate_noise_value,
        #
        cz_unpaired_gate_px=gate_noise_value,
        cz_unpaired_gate_py=gate_noise_value,
        cz_unpaired_gate_pz=gate_noise_value,
        cz_unpaired_loss_prob=gate_noise_value,
    )

    move_noise_params = native.model.MoveNoiseParams(
        idle_px_rate=move_noise_value,
        idle_py_rate=move_noise_value,
        idle_pz_rate=move_noise_value,
        idle_loss_rate=move_noise_value,
        move_px_rate=move_noise_value,
        move_py_rate=move_noise_value,
        move_pz_rate=move_noise_value,
        move_loss_rate=move_noise_value,
        #
        pick_px=move_noise_value,
        pick_py=move_noise_value,
        pick_pz=move_noise_value,
        pick_loss_prob=move_noise_value,
        #
        move_speed=5e-1,  # default 5e-1
        storage_spacing=4.0,  # default 4.0
    )

    with pytest.raises(ir.ValidationError):
        NoisePass(
            entry.dialects,
            gate_noise_params=gate_noise_params,
            noise_model=native.TwoRowZoneModel(params=move_noise_params),
        )(entry)
