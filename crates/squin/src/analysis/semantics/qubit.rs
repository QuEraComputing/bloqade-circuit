//! Give the qubit statements their forward rules.

use kirin_interpreter::dialect::{
    ForwardEval, Interpretable, SparseForwardEffect, SparseForwardInterp,
};

use crate::analysis::QuantumValue;
use crate::ir::dialects::qubit::{Alloc, Free, Measure, Reset};

impl<I> Interpretable<I, ForwardEval> for Alloc
where
    I: SparseForwardInterp,
    I::Value: QuantumValue,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let qubit = I::Value::qubit(interp.statement(), 0);
        interp.write(self.wire, qubit)?;
        Ok(SparseForwardEffect::Next)
    }
}

impl<I: SparseForwardInterp> Interpretable<I, ForwardEval> for Free {
    fn interpret(&self, _interp: &mut I) -> Result<I::Effect, I::Error> {
        Ok(SparseForwardEffect::Next)
    }
}

impl<I> Interpretable<I, ForwardEval> for Measure
where
    I: SparseForwardInterp,
    I::Value: QuantumValue,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let qubit = interp.read(self.wire)?;
        interp.write(self.wire_out, qubit)?;
        interp.write(self.result, I::Value::untracked())?;
        Ok(SparseForwardEffect::Next)
    }
}

impl<I: SparseForwardInterp> Interpretable<I, ForwardEval> for Reset {
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let qubit = interp.read(self.wire)?;
        interp.write(self.wire_out, qubit)?;
        Ok(SparseForwardEffect::Next)
    }
}
