//! Find the qubit that each wire carries.
//!
//! The analysis runs Kirin's sparse forward engine over one function with the
//! `Address` domain. `alloc` names a fresh qubit by its statement, a gate passes
//! the qubit of each input wire to its output wire, and a `borrow` at a known
//! index takes the qubit of that register element. Integer constants and
//! arithmetic on them stay known, so a computed index such as `add %i, %one`
//! still selects one element.
//!
//! An emitter for a target with fixed qubit numbers, such as Stim, reads the
//! facts. A wire whose fact is `Top` has no fixed qubit, for example after a
//! `borrow` at a loop index.

mod bitwise;
mod classical;
mod value;

use kirin::prelude::*;
use kirin_arith::interpreter::DivisionByZero;
use kirin_bitwise::interpreter::ShiftOverflow;
use kirin_interpreter::InterpreterError;
use kirin_interpreter::engine::{
    AbstractBlockFrame, AbstractCallFrame, AbstractDiGraphFrame, AnalysisResults, Analyzed, Frame,
    LinkTarget, SparseForwardInterpreter,
};
use kirin_scf::{AbstractScfForFrame, AbstractScfIfFrame};

use crate::analysis::{ConditionalFrame, RepeatFrame};
use crate::ir::Squin;
pub use value::{Address, QubitId};

/// Hold the frames that the engine stacks while it walks a squin function.
///
/// Squin uses `kirin-scf`, whose `if` and `for` push their own frames, and
/// the squin `conditional` and `repeat` push a `ConditionalFrame` and a
/// `RepeatFrame`.
#[derive(Frame)]
pub enum AddressFrame<V, E> {
    Block(AbstractBlockFrame<V, E>),
    Call(AbstractCallFrame<V, E>),
    DiGraph(AbstractDiGraphFrame<V, E>),
    ScfIf(AbstractScfIfFrame<V, E>),
    ScfFor(AbstractScfForFrame<V, E>),
    Conditional(ConditionalFrame<V, E>),
    Repeat(RepeatFrame<V, E>),
}

/// Tell why the address analysis stopped.
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum AddressError {
    #[error(transparent)]
    Interpreter(#[from] InterpreterError),
    #[error("The function divides a known integer by zero.")]
    DivisionByZero(#[from] DivisionByZero),
    #[error("The function shifts a known integer out of its range.")]
    ShiftOverflow(#[from] ShiftOverflow),
    #[error("The function @{function} has {count} specializations, and the analysis needs one.")]
    Specializations { function: String, count: usize },
}

impl From<std::convert::Infallible> for AddressError {
    fn from(never: std::convert::Infallible) -> Self {
        match never {}
    }
}

type Engine<'ir> = SparseForwardInterpreter<
    'ir,
    StageInfo<Squin>,
    Address,
    AddressError,
    kirin_interpreter::SameStageLinker,
    kirin_interpreter::ContextInsensitive,
    AddressFrame<Address, AddressError>,
>;

/// Hold the converged facts of one analyzed function.
pub struct Addresses<'ir> {
    analyzed: Analyzed<Engine<'ir>>,
    function: LinkTarget,
    definition: Statement,
}

impl Addresses<'_> {
    /// Return the definition statement of the analyzed function.
    pub fn definition(&self) -> Statement {
        self.definition
    }

    /// Return the fact of `value`.
    ///
    /// The fact joins every context of the function that the analysis reached.
    /// A value that the analysis never reached has the fact `Bottom`.
    pub fn of(&self, value: impl Into<SSAValue>) -> Address {
        let fact = self.analyzed.joined_fact(self.function, value.into());
        fact.unwrap_or(Address::Bottom)
    }
}

/// Analyze the function `function` of the stage `stage`.
///
/// Each argument of the function gets the fact `Top`, so a fact that holds
/// holds for every call.
pub fn analyze<'ir>(
    pipeline: &'ir Pipeline<StageInfo<Squin>>,
    stage: &str,
    function: &str,
) -> Result<Addresses<'ir>, AddressError> {
    let stage_id = pipeline
        .stage_by_name(stage)
        .ok_or_else(|| InterpreterError::MissingStageName(stage.into()))?;
    let (arity, definition) = signature(pipeline, stage_id, function)?;
    let arguments = std::iter::repeat_n(Address::Top, arity);
    let analyzed = Engine::new(pipeline).analyze_by_name(stage, function, arguments)?;
    let root = *analyzed.root();
    let function = analyzed
        .callable_of(&root)
        .ok_or_else(|| InterpreterError::MissingFunctionName(function.into()))?;
    Ok(Addresses {
        analyzed,
        function,
        definition,
    })
}

/// Return the number of parameters and the definition of the function `function` in `stage`.
fn signature(
    pipeline: &Pipeline<StageInfo<Squin>>,
    stage: CompileStage,
    function: &str,
) -> Result<(usize, Statement), AddressError> {
    let missing = || InterpreterError::MissingFunctionName(function.into());
    let staged = pipeline
        .resolve_staged_function(function, stage)
        .ok_or_else(missing)?;
    let program = pipeline.stage(stage).ok_or_else(missing)?;
    let info = program
        .staged_function_arena()
        .get(staged)
        .ok_or_else(missing)?;
    let [definition] = info.specializations() else {
        let (function, count) = (function.to_string(), info.specializations().len());
        return Err(AddressError::Specializations { function, count });
    };
    Ok((info.signature().params().len(), *definition.definition()))
}
