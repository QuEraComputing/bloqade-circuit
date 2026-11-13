//! Give the register statements their forward rules.

use kirin_interpreter::dialect::{
    ForwardEval, Interpretable, SparseForwardEffect, SparseForwardInterp,
};

use crate::analysis::QuantumValue;
use crate::ir::dialects::register::{
    AllocRegister, Borrow, FreeRegister, Join, LengthOf, MeasureRegister, Pack, Release, Replace,
    Split,
};

impl<I> Interpretable<I, ForwardEval> for AllocRegister
where
    I: SparseForwardInterp,
    I::Value: QuantumValue,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let size = interp.read(self.size)?;
        let register = I::Value::allocated_register(interp.statement(), &size);
        interp.write(self.register, register)?;
        Ok(SparseForwardEffect::Next)
    }
}

impl<I: SparseForwardInterp> Interpretable<I, ForwardEval> for FreeRegister {
    fn interpret(&self, _interp: &mut I) -> Result<I::Effect, I::Error> {
        Ok(SparseForwardEffect::Next)
    }
}

impl<I> Interpretable<I, ForwardEval> for Pack
where
    I: SparseForwardInterp,
    I::Value: QuantumValue,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let wires = self.wires.iter().map(|wire| interp.read(*wire));
        let register = I::Value::packed(wires.collect::<Result<_, _>>()?);
        interp.write(self.register, register)?;
        Ok(SparseForwardEffect::Next)
    }
}

impl<I> Interpretable<I, ForwardEval> for Split
where
    I: SparseForwardInterp,
    I::Value: QuantumValue,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let (register, index) = (interp.read(self.register)?, interp.read(self.index)?);
        let (before, after) = I::Value::split_at(&register, &index);
        interp.write(self.before, before)?;
        interp.write(self.after, after)?;
        Ok(SparseForwardEffect::Next)
    }
}

impl<I> Interpretable<I, ForwardEval> for Join
where
    I: SparseForwardInterp,
    I::Value: QuantumValue,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let (first, second) = (interp.read(self.first)?, interp.read(self.second)?);
        interp.write(self.register, I::Value::concatenated(&first, &second))?;
        Ok(SparseForwardEffect::Next)
    }
}

impl<I> Interpretable<I, ForwardEval> for LengthOf
where
    I: SparseForwardInterp,
    I::Value: QuantumValue,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let register = interp.read(self.register)?;
        interp.write(self.length, I::Value::length(&register))?;
        interp.write(self.register_out, register)?;
        Ok(SparseForwardEffect::Next)
    }
}

impl<I> Interpretable<I, ForwardEval> for MeasureRegister
where
    I: SparseForwardInterp,
    I::Value: QuantumValue,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let register = interp.read(self.register)?;
        interp.write(self.register_out, register)?;
        interp.write(self.results, I::Value::untracked())?;
        Ok(SparseForwardEffect::Next)
    }
}

/// Lend the element at the index, and leave the register value unchanged.
///
/// The verifier proves that the matching `release` returns the same qubit to
/// the same element, so the register holds the same qubits after the pair.
impl<I> Interpretable<I, ForwardEval> for Borrow
where
    I: SparseForwardInterp,
    I::Value: QuantumValue,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let (register, index) = (interp.read(self.register)?, interp.read(self.index)?);
        interp.write(self.wire, I::Value::element(&register, &index))?;
        interp.write(self.slot, I::Value::untracked())?;
        interp.write(self.register_out, register)?;
        Ok(SparseForwardEffect::Next)
    }
}

impl<I: SparseForwardInterp> Interpretable<I, ForwardEval> for Release {
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let register = interp.read(self.register)?;
        interp.write(self.register_out, register)?;
        Ok(SparseForwardEffect::Next)
    }
}

impl<I> Interpretable<I, ForwardEval> for Replace
where
    I: SparseForwardInterp,
    I::Value: QuantumValue,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let (register, index) = (interp.read(self.register)?, interp.read(self.index)?);
        let wire = interp.read(self.wire)?;
        let (register, old) = I::Value::replaced(&register, &index, wire);
        interp.write(self.register_out, register)?;
        interp.write(self.wire_out, old)?;
        Ok(SparseForwardEffect::Next)
    }
}
