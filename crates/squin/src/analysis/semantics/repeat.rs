//! Give the repeat loop its forward rule and the frame that runs its body to a fixpoint.

use std::marker::PhantomData;

use kirin::prelude::{Block, CompileStage, Lattice, Product, SSAValue};
use kirin_interpreter::dialect::{
    ForwardEval, Interpretable, SparseForwardEffect, SparseForwardInterp,
};
use kirin_interpreter::{
    AbstractBlockFrame, AbstractCompletion, BranchCondition, EnvIndex, ForwardDataflowFrameEngine,
    Frame, FrameEffect, InterpreterError,
};

use crate::ir::dialects::repeat::Repeat;

/// Push a frame that runs the body until its carried facts stop changing.
impl<I> Interpretable<I, ForwardEval> for Repeat
where
    I: SparseForwardInterp,
    I::Value: BranchCondition + PartialEq,
    I::Error: From<InterpreterError>,
    I::Frame: From<RepeatFrame<I::Value, I::Error>>,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let inputs = interp.read_many(&self.inputs)?;
        let frame = RepeatFrame::new(interp.stage(), interp.index(), self.body, inputs);
        let results: Product<SSAValue> = self.results.iter().copied().map(Into::into).collect();
        Ok(SparseForwardEffect::Push {
            frame: frame.into(),
            results,
        })
    }
}

/// Run the body on the carried facts and join each run's yields into them.
///
/// The body can run any number of times, so the facts at its entry join the
/// inputs with the values of every earlier run. The frame stops when a run
/// yields a true stop flag or leaves the entry facts unchanged. The results
/// join the carried values of each run whose stop flag can be true.
pub struct RepeatFrame<V, E> {
    stage: CompileStage,
    index: EnvIndex,
    body: Block,
    entry: Product<V>,
    results: Option<Product<V>>,
    runs: usize,
    done: bool,
    _error: PhantomData<fn() -> E>,
}

impl<V, E> RepeatFrame<V, E> {
    fn new(stage: CompileStage, index: EnvIndex, body: Block, inputs: Product<V>) -> Self {
        Self {
            stage,
            index,
            body,
            entry: inputs,
            results: None,
            runs: 0,
            done: false,
            _error: PhantomData,
        }
    }
}

impl<I, F, V, E> Frame<I, F> for RepeatFrame<V, E>
where
    I: ForwardDataflowFrameEngine<Value = V, Error = E>,
    F: From<AbstractBlockFrame<V, E>>,
    V: Clone + PartialEq + Lattice + BranchCondition,
    E: From<InterpreterError>,
{
    type Completion = AbstractCompletion<V>;

    fn step_into(self, _interp: &mut I) -> Result<FrameEffect<Self, Self::Completion, F>, E> {
        if self.done {
            return Ok(FrameEffect::Complete(AbstractCompletion::Finished(
                self.results,
            )));
        }
        let body = AbstractBlockFrame::new(self.stage, self.index, self.body, self.entry.clone());
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
            "a repeat body finished without a yield",
        )))
    }

    fn resume_into(
        mut self,
        completion: Self::Completion,
        interp: &mut I,
    ) -> Result<FrameEffect<Self, Self::Completion, F>, E> {
        let values = match completion {
            AbstractCompletion::Finished(Some(values)) => values,
            // The body returned from the function, so no run reaches the results.
            AbstractCompletion::Finished(None) => {
                self.done = true;
                return Ok(FrameEffect::Continue(self));
            }
            _ => {
                return Err(E::from(InterpreterError::Custom(
                    "a repeat body finished in a way that a yield cannot",
                )));
            }
        };
        let mut yielded = values.into_iter();
        let stop = yielded.next().map(|flag| flag.is_truthy());
        let carried: Product<V> = yielded.collect();
        self.runs += 1;
        if stop != Some(Some(false)) {
            self.results = Some(match self.results.take() {
                None => carried.clone(),
                Some(results) => interp.analysis_merge(&results, &carried, self.runs)?,
            });
        }
        let entry = interp.analysis_merge(&self.entry, &carried, self.runs)?;
        self.done = stop == Some(Some(true)) || entry == self.entry;
        self.entry = entry;
        Ok(FrameEffect::Continue(self))
    }
}
