//! Give the circuit region its forward rule.

use kirin::prelude::{Product, SSAValue};
use kirin_interpreter::dialect::{
    ForwardEval, Interpretable, SparseForwardEffect, SparseForwardInterp,
};
use kirin_interpreter::{AbstractDiGraphFrame, InterpreterError};

use crate::ir::dialects::circuit::Circuit;

/// Walk the region graph with the facts of the inputs, and bind its yields to the results.
///
/// Kirin's sparse forward engine walks the graph in dependency order. The rule
/// needs an engine whose frames include `AbstractDiGraphFrame`.
impl<I> Interpretable<I, ForwardEval> for Circuit
where
    I: SparseForwardInterp,
    I::Value: PartialEq,
    I::Error: From<InterpreterError>,
    I::Frame: From<AbstractDiGraphFrame<I::Value, I::Error>>,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let inputs = interp.read_many(&self.inputs)?;
        let frame = AbstractDiGraphFrame::new(interp.stage(), interp.index(), self.body, inputs);
        let results: Product<SSAValue> = self.results.iter().copied().map(Into::into).collect();
        Ok(SparseForwardEffect::Push {
            frame: frame.into(),
            results,
        })
    }
}
