//! Write the circuit instructions that gates, allocations and measurements share.

use kirin::prelude::*;

use super::PpvmEmitter;
use super::PpvmError;
use super::locals::Slot;
use super::operand::Operand;
use crate::ir::traits::Threads;

impl PpvmEmitter<'_> {
    /// Write the circuit instruction `name` for `gate`.
    ///
    /// ppvm pops the angles first and the qubits after them, so the emitter
    /// pushes each qubit index and then each angle. A squin angle is in
    /// turns, and ppvm rotates by `exp(-i θ/2 · P)` with θ in radians. So the
    /// emitter multiplies each angle by `tau` on the CPU stack.
    pub(super) fn gate(
        &mut self,
        gate: &impl Threads,
        name: &str,
        angles: &[SSAValue],
    ) -> Result<(), PpvmError> {
        for operand in self.operands(gate)? {
            self.push(operand);
        }
        for angle in angles {
            self.load(*angle)?;
            self.line(format!("cpu::cpu.const f64, {:?}", std::f64::consts::TAU));
            self.line("cpu::cpu.mul f64".to_string());
        }
        self.line(format!("circuit::circuit.{name}"));
        self.continue_wires(gate)
    }

    /// Push each qubit operand and run the circuit instruction `name`.
    pub(super) fn qubit_instruction(&mut self, name: &str, qubits: &[Operand]) {
        for qubit in qubits {
            self.push(*qubit);
        }
        self.line(format!("circuit::circuit.{name}"));
    }

    /// Give an index to each qubit of `value`, and reset a qubit that can hold a state.
    ///
    /// A reused index holds the state of a freed qubit. In a loop, a fresh
    /// index holds the state of the previous run.
    pub(super) fn allocate(&mut self, value: SSAValue) -> Result<(), PpvmError> {
        for (index, reused) in self.qubits.allocate(value)? {
            if reused || self.loops > 0 {
                self.qubit_instruction("reset", &[Operand::Fixed(index)]);
            }
        }
        Ok(())
    }

    /// Measure the qubit `qubit` and store the outcome in `slot`.
    pub(super) fn measure(&mut self, qubit: Operand, slot: Slot) {
        self.qubit_instruction("measure", &[qubit]);
        self.store_into(&[slot]);
    }
}
