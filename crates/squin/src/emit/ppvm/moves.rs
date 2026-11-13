//! Move classical values between the CPU stack and their local slots.

use kirin::prelude::*;

use super::PpvmError;
use super::locals::Slot;
use super::writer::Writer;
use crate::ir::query;

impl Writer<'_> {
    /// Give `value` new slots for its type, and return them.
    pub(super) fn define(&mut self, value: SSAValue) -> Vec<Slot> {
        let ty = *value.expect_info(self.program).ty();
        self.locals.define(value, ty)
    }

    /// Push the value of the classical `value` from its slot.
    pub(super) fn load(&mut self, value: SSAValue) -> Result<(), PpvmError> {
        let slots = self.slots(value)?;
        for (slot, kind) in slots {
            self.line(format!("cpu::cpu.load {kind}, {slot}"));
        }
        Ok(())
    }

    /// Pop the top of the stack into the slots of `value`.
    pub(super) fn store(&mut self, value: SSAValue) -> Result<(), PpvmError> {
        let slots = self.slots(value)?;
        for (slot, kind) in slots.into_iter().rev() {
            self.line(format!("cpu::cpu.store {kind}, {slot}"));
        }
        Ok(())
    }

    /// Return the slots of the classical `value`.
    pub(super) fn slots(&self, value: SSAValue) -> Result<Vec<Slot>, PpvmError> {
        self.locals.get(value).map(<[Slot]>::to_vec).ok_or_else(|| {
            let name = query::name(self.program, value);
            PpvmError::Unsupported(format!("the value {name} before its definition"))
        })
    }

    /// Copy each value of `sources` into the slots of the target at its position.
    ///
    /// The writer loads every source before it stores any target, so a
    /// target may be a source too, as in a loop that swaps two values.
    pub(super) fn copy(
        &mut self,
        sources: &[SSAValue],
        targets: &[Vec<Slot>],
    ) -> Result<(), PpvmError> {
        let mut stored = Vec::new();
        for (source, target) in sources.iter().zip(targets) {
            if !target.is_empty() {
                self.load(*source)?;
                stored.push(target.clone());
            }
        }
        for target in stored.into_iter().rev() {
            for (slot, kind) in target.into_iter().rev() {
                self.line(format!("cpu::cpu.store {kind}, {slot}"));
            }
        }
        Ok(())
    }
}
