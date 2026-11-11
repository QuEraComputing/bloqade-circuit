//! Give one entry point for the work on a squin program.

use kirin::parsers::FunctionParseError;
use kirin::prelude::*;

use crate::language::Squin;
use crate::passes;
use crate::run::{Backend, Failure, Machine, Value};
use crate::stim::Stim;
use crate::verify::{Verified, Violation, verify};

/// Hold a squin program that the verifier accepts.
///
/// ```text
/// let mut kernel = Kernel::parse(text)?;
/// kernel.optimize()?;
/// let circuit = kernel.to_stim("main")?;
/// ```
pub struct Kernel {
    pipeline: Pipeline<StageInfo<Squin>>,
    stage: CompileStage,
}

impl Kernel {
    /// Parse `text` in the Kirin text format and verify the program.
    ///
    /// The text must declare one stage.
    pub fn parse(text: &str) -> Result<Self, KernelError> {
        let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
        pipeline.parse(text).map_err(KernelError::Parse)?;
        let stages: Vec<CompileStage> = pipeline.stage_names().map(|(stage, _)| stage).collect();
        let [stage] = stages[..] else {
            return Err(KernelError::Stages);
        };
        let kernel = Self { pipeline, stage };
        verify(kernel.stage()?).map_err(KernelError::Invalid)?;
        Ok(kernel)
    }

    /// Run the rewrite passes and return the number of rewrites.
    pub fn optimize(&mut self) -> Result<usize, KernelError> {
        let rewrites = passes::simplify(&mut self.pipeline, self.stage);
        let rewrites = rewrites.map_err(KernelError::Pass)?;
        verify(self.stage()?).map_err(KernelError::Invalid)?;
        Ok(rewrites)
    }

    /// Return the program in the Kirin text format.
    pub fn text(&self) -> String {
        self.pipeline.sprint()
    }

    /// Run the function `name` on `backend` and return the values that it returns.
    pub fn run<B: Backend>(
        &self,
        name: &str,
        arguments: Vec<Value<B::Bit>>,
        backend: &mut B,
    ) -> Result<Vec<Value<B::Bit>>, KernelError> {
        // `parse` and `optimize` verify the program, and no other method changes it.
        let program = Verified::trusted(self.stage()?);
        let entry = self.entry(name)?;
        Ok(Machine::new(program, backend).block(entry, arguments)?)
    }

    /// Write the function `name` as a Stim circuit.
    ///
    /// The function must take no arguments.
    pub fn to_stim(&self, name: &str) -> Result<String, KernelError> {
        let mut stim = Stim::default();
        self.run(name, Vec::new(), &mut stim)?;
        Ok(stim.finish())
    }

    fn stage(&self) -> Result<&StageInfo<Squin>, KernelError> {
        self.pipeline.stage(self.stage).ok_or(KernelError::Unusable)
    }

    /// Return the first block of the body of the function `name`.
    fn entry(&self, name: &str) -> Result<Block, KernelError> {
        let program = self.stage()?;
        let function = self.pipeline.lookup_function_by_name(name);
        let staged = function
            .and_then(|function| self.pipeline.function_info(function))
            .and_then(|info| info.staged_function(self.stage))
            .and_then(|staged| program.staged_function_arena().get(staged));
        let definition = staged.and_then(|staged| staged.specializations().first());
        let mut bodies = definition
            .into_iter()
            .flat_map(|body| body.definition().cfgs(program));
        let entry = bodies.next().and_then(|cfg| cfg.blocks(program).next());
        entry.ok_or_else(|| KernelError::UnknownFunction(name.to_string()))
    }
}

/// Tell why a step on a `Kernel` did not succeed.
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum KernelError {
    #[error("The text is not a squin program: {0}")]
    Parse(#[source] FunctionParseError),
    #[error("The text must declare one stage.")]
    Stages,
    #[error("{}", lines(.0))]
    Invalid(Vec<Violation>),
    #[error("A rewrite pass stopped before its end: {0}")]
    Pass(#[source] StagePassError),
    #[error("A failed pass left the program unusable.")]
    Unusable,
    #[error("The program has no function @{0}.")]
    UnknownFunction(String),
    #[error(transparent)]
    Run(#[from] Failure),
}

/// Return the violations with one on each line.
fn lines(violations: &[Violation]) -> String {
    let lines: Vec<String> = violations.iter().map(Violation::to_string).collect();
    lines.join("\n")
}
