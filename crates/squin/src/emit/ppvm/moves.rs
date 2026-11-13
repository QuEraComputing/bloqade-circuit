//! Move classical values between the CPU stack and their local slots.

use kirin::prelude::*;
use kirin_interpreter::Env;

use super::PpvmEmitter;
use super::PpvmError;
use super::locals::{Kind, Slot, kinds};
use crate::ir::types::SquinType;

impl PpvmEmitter<'_> {
    /// Give `value` new slots for its type, and return them.
    ///
    /// The result is empty for a quantum value, which has no slot.
    pub(super) fn define(&mut self, value: SSAValue) -> Result<Vec<Slot>, PpvmError> {
        let ty = *value.expect_info(self.program).ty();
        let slots: Vec<Slot> = kinds(ty)
            .into_iter()
            .map(|kind| self.fresh_slot(kind))
            .collect();
        if !slots.is_empty() {
            self.set(value, slots.clone())?;
        }
        Ok(slots)
    }

    /// Give `value` the slots that carry it into a loop body or out of a branch.
    ///
    /// A classical value gets slots for its type. A wire whose qubit the
    /// address analysis does not know gets one `u64` slot for its qubit index,
    /// because that index can differ from run to run. A wire with a known
    /// qubit needs no slot.
    pub(super) fn define_carried(&mut self, value: SSAValue) -> Result<Vec<Slot>, PpvmError> {
        let ty = *value.expect_info(self.program).ty();
        if ty != SquinType::Wire || self.qubits.index(value).is_ok() {
            return self.define(value);
        }
        let slot = self.fresh_slot(Kind::U64);
        self.set(value, vec![slot])?;
        Ok(vec![slot])
    }

    /// Push `value` onto the stack: the qubit index of a wire, or the slots of a classical value.
    pub(super) fn push_value(&mut self, value: SSAValue) -> Result<(), PpvmError> {
        if *value.expect_info(self.program).ty() == SquinType::Wire {
            let operand = self.operand(value)?;
            self.push(operand);
            return Ok(());
        }
        self.load(value)
    }

    /// Reserve one new slot of kind `kind` that no SSA value owns yet.
    pub(super) fn fresh_slot(&mut self, kind: Kind) -> Slot {
        self.slots += 1;
        (self.slots - 1, kind)
    }

    /// Return the slots of the classical `value`.
    pub(super) fn slots_of(&self, value: SSAValue) -> Result<Vec<Slot>, PpvmError> {
        self.env_read(self.index, value)
    }

    /// Let `value` use `slots`.
    pub(super) fn set(&mut self, value: SSAValue, slots: Vec<Slot>) -> Result<(), PpvmError> {
        self.env_write(self.index, value, slots)
    }

    /// Let `value` share the slots of `target`, as a port shares its input.
    ///
    /// A quantum `target` has no slots, so `value` gets none either.
    pub(super) fn alias(&mut self, value: SSAValue, target: SSAValue) -> Result<(), PpvmError> {
        if let Some(slots) = self.env.read(self.index, target)? {
            self.set(value, slots)?;
        }
        Ok(())
    }

    /// Push the value of the classical `value` from its slots.
    pub(super) fn load(&mut self, value: SSAValue) -> Result<(), PpvmError> {
        for (slot, kind) in self.slots_of(value)? {
            self.line(format!("cpu::cpu.load {kind}, {slot}"));
        }
        Ok(())
    }

    /// Pop the top of the stack into `slots`.
    pub(super) fn store_into(&mut self, slots: &[Slot]) {
        for (slot, kind) in slots.iter().rev() {
            self.line(format!("cpu::cpu.store {kind}, {slot}"));
        }
    }

    /// Give `result` slots and pop the top of the stack into them.
    pub(super) fn result(&mut self, result: SSAValue) -> Result<(), PpvmError> {
        let slots = self.define(result)?;
        self.store_into(&slots);
        Ok(())
    }

    /// Load `operands`, run the CPU instruction `name` with the kind of `result`, and store it.
    pub(super) fn typed(
        &mut self,
        operands: &[SSAValue],
        result: SSAValue,
        name: &str,
    ) -> Result<(), PpvmError> {
        for operand in operands {
            self.load(*operand)?;
        }
        let kind = self.kind(result)?;
        self.line(format!("cpu::cpu.{name} {kind}"));
        self.result(result)
    }

    /// Return the kind of the classical `value`.
    pub(super) fn kind(&self, value: SSAValue) -> Result<Kind, PpvmError> {
        let ty = *value.expect_info(self.program).ty();
        Kind::of(ty)
            .ok_or_else(|| PpvmError::Unsupported(format!("a classical value of type {ty}")))
    }

    /// Copy each value of `sources` into the slots of the target at its position.
    ///
    /// A source wire copies its qubit index, as a constant or from its slot.
    ///
    /// The emitter loads every source before it stores any target, so a
    /// target may be a source too, as in a loop that swaps two values.
    pub(super) fn copy(
        &mut self,
        sources: &[SSAValue],
        targets: &[Vec<Slot>],
    ) -> Result<(), PpvmError> {
        let mut stored = Vec::new();
        for (source, target) in sources.iter().zip(targets) {
            if !target.is_empty() {
                self.push_value(*source)?;
                stored.push(target.clone());
            }
        }
        for target in stored.into_iter().rev() {
            self.store_into(&target);
        }
        Ok(())
    }
}
