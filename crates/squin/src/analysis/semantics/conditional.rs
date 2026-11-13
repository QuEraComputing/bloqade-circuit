//! Give the conditional its forward rule and the frame that runs its arms.

use std::collections::VecDeque;
use std::marker::PhantomData;

use kirin::prelude::{Block, CompileStage, Lattice, Product, SSAValue};
use kirin_interpreter::dialect::{
    ForwardEval, Interpretable, SparseForwardEffect, SparseForwardInterp,
};
use kirin_interpreter::{
    AbstractBlockFrame, AbstractCompletion, BranchCondition, EnvIndex, ForwardDataflowFrameEngine,
    Frame, FrameEffect, InterpreterError,
};

use crate::ir::dialects::conditional::Conditional;

/// Push a frame that runs the arm that the condition selects, or both arms.
impl<I> Interpretable<I, ForwardEval> for Conditional
where
    I: SparseForwardInterp,
    I::Value: BranchCondition + PartialEq,
    I::Error: From<InterpreterError>,
    I::Frame: From<ConditionalFrame<I::Value, I::Error>>,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let arms = match interp.read(self.condition)?.is_truthy() {
            Some(true) => vec![self.then_body],
            Some(false) => vec![self.else_body],
            None => vec![self.then_body, self.else_body],
        };
        let inputs = interp.read_many(&self.inputs)?;
        let frame = ConditionalFrame::new(interp.stage(), interp.index(), arms, inputs);
        let results: Product<SSAValue> = self.results.iter().copied().map(Into::into).collect();
        Ok(SparseForwardEffect::Push {
            frame: frame.into(),
            results,
        })
    }
}

/// Run each remaining arm with the inputs as its arguments, and join the yields.
///
/// Kirin's `AbstractScfIfFrame` enters its arms with no arguments, so the
/// conditional needs this frame to hand its wires to the arms.
pub struct ConditionalFrame<V, E> {
    stage: CompileStage,
    index: EnvIndex,
    arms: VecDeque<Block>,
    inputs: Product<V>,
    joined: Option<Product<V>>,
    _error: PhantomData<fn() -> E>,
}

impl<V, E> ConditionalFrame<V, E> {
    fn new(stage: CompileStage, index: EnvIndex, arms: Vec<Block>, inputs: Product<V>) -> Self {
        Self {
            stage,
            index,
            arms: arms.into(),
            inputs,
            joined: None,
            _error: PhantomData,
        }
    }
}

impl<I, F, V, E> Frame<I, F> for ConditionalFrame<V, E>
where
    I: ForwardDataflowFrameEngine<Value = V, Error = E>,
    F: From<AbstractBlockFrame<V, E>>,
    V: Clone + PartialEq + Lattice,
    E: From<InterpreterError>,
{
    type Completion = AbstractCompletion<V>;

    fn step_into(mut self, _interp: &mut I) -> Result<FrameEffect<Self, Self::Completion, F>, E> {
        let Some(arm) = self.arms.pop_front() else {
            return Ok(FrameEffect::Complete(AbstractCompletion::Finished(
                self.joined,
            )));
        };
        let body = AbstractBlockFrame::new(self.stage, self.index, arm, self.inputs.clone());
        Ok(FrameEffect::Push {
            parent: self,
            child: body.into(),
        })
    }

    fn resume_done_into(
        self,
        _interp: &mut I,
    ) -> Result<FrameEffect<Self, Self::Completion, F>, E> {
        Err(E::from(InterpreterError::Custom(
            "a conditional arm finished without a yield",
        )))
    }

    fn resume_into(
        mut self,
        completion: Self::Completion,
        interp: &mut I,
    ) -> Result<FrameEffect<Self, Self::Completion, F>, E> {
        match completion {
            AbstractCompletion::Finished(Some(values)) => {
                self.joined = Some(match self.joined.take() {
                    None => values,
                    Some(joined) => interp.analysis_merge(&joined, &values, 0)?,
                });
                Ok(FrameEffect::Continue(self))
            }
            // The arm returned from the function, so it yields nothing here.
            AbstractCompletion::Finished(None) => Ok(FrameEffect::Continue(self)),
            _ => Err(E::from(InterpreterError::Custom(
                "a conditional arm finished in a way that a yield cannot",
            ))),
        }
    }
}
