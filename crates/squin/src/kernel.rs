//! Give one entry point for the work on a squin program.

use std::fmt;

use kirin::prelude::*;

use crate::language::Squin;
use crate::passes;
use crate::run::{Backend, Failure, Machine, Value};
use crate::stim::Stim;
use crate::verify::{Violation, verify};

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
        let parsed = pipeline.parse(text);
        parsed.map_err(|error| KernelError::Parse(error.to_string()))?;
        let stages: Vec<CompileStage> = pipeline.stage_names().map(|(stage, _)| stage).collect();
        let [stage] = stages[..] else {
            return Err(KernelError::Parse(
                "The text must declare one stage.".into(),
            ));
        };
        let kernel = Self { pipeline, stage };
        verify(kernel.program()?).map_err(KernelError::Invalid)?;
        Ok(kernel)
    }

    /// Run the rewrite passes and return the number of rewrites.
    pub fn optimize(&mut self) -> Result<usize, KernelError> {
        let rewrites = passes::simplify(&mut self.pipeline, self.stage);
        let rewrites = rewrites.map_err(|error| KernelError::Pass(format!("{error:?}")))?;
        verify(self.program()?).map_err(KernelError::Invalid)?;
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
        let program = self.program()?;
        let entry = self.entry(name)?;
        let returned = Machine::new(program, backend).block(entry, arguments);
        returned.map_err(KernelError::Run)
    }

    /// Write the function `name` as a Stim circuit.
    ///
    /// The function must take no arguments.
    pub fn to_stim(&self, name: &str) -> Result<String, KernelError> {
        let mut stim = Stim::default();
        self.run(name, Vec::new(), &mut stim)?;
        Ok(stim.finish())
    }

    fn program(&self) -> Result<&StageInfo<Squin>, KernelError> {
        let unusable = || KernelError::Pass("A failed pass left the program unusable.".into());
        self.pipeline.stage(self.stage).ok_or_else(unusable)
    }

    /// Return the first block of the body of the function `name`.
    fn entry(&self, name: &str) -> Result<Block, KernelError> {
        let program = self.program()?;
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
#[derive(Debug)]
pub enum KernelError {
    /// The text is not a squin program.
    Parse(String),
    /// The program breaks the verifier rules.
    Invalid(Vec<Violation>),
    /// A rewrite pass stopped before its end.
    Pass(String),
    /// The program has no function of this name.
    UnknownFunction(String),
    /// The evaluator stopped before the end of the function.
    Run(Failure),
}

impl fmt::Display for KernelError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            KernelError::Parse(message) | KernelError::Pass(message) => write!(f, "{message}"),
            KernelError::Invalid(violations) => {
                let lines: Vec<String> = violations.iter().map(Violation::to_string).collect();
                write!(f, "{}", lines.join("\n"))
            }
            KernelError::UnknownFunction(name) => write!(f, "The program has no function @{name}."),
            KernelError::Run(failure) => write!(f, "{failure}"),
        }
    }
}

impl std::error::Error for KernelError {}
