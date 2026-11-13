//! Write a squin function as a Stim circuit.
//!
//! The emitter is a Kirin interpreter. [`EmitStim`] is its semantic key, and
//! [`StimEmitter`] is its engine. Each statement has an
//! `Interpretable<StimEmitter, EmitStim>` rule in `rules`, and the derived
//! `Interpretable` of the wrapper enums dispatches to it.
//!
//! The emitter verifies the stage and runs the address analysis. Each wire
//! must carry a known qubit, so the function needs constant register sizes
//! and constant indices. Stim has no loops over squin values and no branches,
//! so a `for` and a `repeat` are errors, and an `if` or a `conditional` needs
//! a condition that the analysis knows. A `circuit` region emits its graph in
//! dependency order.
//!
//! The emitter gives each qubit a Stim index. A qubit after a `free` gives its
//! index to the next allocation, which resets it first.

mod engine;
mod error;
mod rules;

use kirin::prelude::*;
use kirin_interpreter::dialect::{SemanticKey, SparseForwardShape};

use crate::analysis::address;
use crate::ir::{Squin, query};
use crate::verify::verify;
pub use engine::StimEmitter;
pub use error::StimError;

/// Name the interpretation that writes Stim instructions for each statement.
pub struct EmitStim;

impl SemanticKey for EmitStim {
    type Shape = SparseForwardShape;
}

/// Write the function `function` of the stage `stage` as a Stim circuit.
///
/// The result holds one instruction on each line.
pub fn emit(
    pipeline: &Pipeline<StageInfo<Squin>>,
    stage: &str,
    function: &str,
) -> Result<String, StimError> {
    let unknown = || StimError::UnknownStage(stage.to_string());
    let id = pipeline.stage_by_name(stage).ok_or_else(unknown)?;
    let program = pipeline.stage(id).ok_or_else(unknown)?;
    verify(program).map_err(StimError::Invalid)?;
    let addresses = address::analyze(pipeline, stage, function)?;
    // Squin bodies hold one block, because `kirin-scf` carries the control flow.
    // A body with more blocks needs branch statements that the walk cannot follow.
    let blocks = query::body_blocks(program, addresses.definition());
    let [entry] = blocks[..] else {
        let count = blocks.len();
        return Err(StimError::Unsupported(format!(
            "a function body with {count} blocks"
        )));
    };
    let mut emitter = StimEmitter::new(program, id, &addresses);
    emitter.block(entry)?;
    Ok(emitter.finish())
}
