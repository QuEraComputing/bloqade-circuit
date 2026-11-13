//! Write a squin function as Python squin code, to read it in a familiar form.
//!
//! The emitter is a Kirin interpreter. [`EmitPython`] is its semantic key,
//! and [`PythonEmitter`] is its engine. A value of the engine is the Python
//! expression that stands for one SSA value.
//!
//! Python squin uses qubit references, and Rust squin uses linear wires. A
//! gate therefore writes one call, such as `squin.h(a)`, and its output wire
//! keeps the name of its input wire. A `circuit` writes its graph in
//! dependency order with no wrapper. A `conditional` becomes `if` and
//! `else`, and a `for` becomes a `for` over `range`. A `repeat` becomes a
//! nested function for its body and a call of `squin.repeat_until_success`.
//! Python squin has no such function, so the output is for reading and may
//! not run.

mod bindings;
mod engine;
mod error;
mod flow;
mod names;
mod rules;
mod value;

use kirin::prelude::*;

use crate::ir::{Squin, query};
use crate::verify::verify;
pub use engine::PythonEmitter;
pub use error::PythonError;
pub use value::Py;

/// Name the interpretation that writes Python squin code for each statement.
pub struct EmitPython;

impl kirin_interpreter::dialect::SemanticKey for EmitPython {
    type Shape = kirin_interpreter::dialect::SparseForwardShape;
}

/// Write the function `function` of the stage `stage` as a Python squin kernel.
pub fn emit(
    pipeline: &Pipeline<StageInfo<Squin>>,
    stage: &str,
    function: &str,
) -> Result<String, PythonError> {
    let unknown = || PythonError::UnknownStage(stage.to_string());
    let id = pipeline.stage_by_name(stage).ok_or_else(unknown)?;
    let program = pipeline.stage(id).ok_or_else(unknown)?;
    verify(program).map_err(PythonError::Invalid)?;
    let missing = || PythonError::UnknownFunction(function.to_string());
    let staged = pipeline
        .resolve_staged_function(function, id)
        .ok_or_else(missing)?;
    let info = program
        .staged_function_arena()
        .get(staged)
        .ok_or_else(missing)?;
    let [specialization] = info.specializations() else {
        let count = info.specializations().len();
        return Err(PythonError::Unsupported(format!(
            "a function with {count} specializations"
        )));
    };
    let blocks = query::body_blocks(program, *specialization.definition());
    let [entry] = blocks[..] else {
        let count = blocks.len();
        return Err(PythonError::Unsupported(format!(
            "a function body with {count} blocks"
        )));
    };
    let mut emitter = PythonEmitter::new(program, id);
    let parameters = emitter.parameters(entry)?;
    emitter.indented(|emitter| emitter.block(entry))?;
    Ok(emitter.finish(function, &parameters))
}
