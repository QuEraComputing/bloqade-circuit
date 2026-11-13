//! Write a squin function as a program for ppvm, QuEra's circuit simulator.
//!
//! ppvm runs programs on vihaco, a stack machine with a `cpu` component for
//! classical work and a `circuit` component for quantum instructions. The
//! emitter writes `.sst` source text, and the `ppvm` feature turns that text
//! into `.ssb` bytecode through `ppvm_vihaco`. The emitter runs nothing.
//!
//! The emitter is a Kirin interpreter. [`EmitPpvm`] is its semantic key, and
//! [`PpvmEmitter`] is its engine. Each statement has an
//! `Interpretable<PpvmEmitter, EmitPpvm>` rule in `rules`, and the derived
//! `Interpretable` of the wrapper enums dispatches to it. A value of the
//! engine is symbolic: it names the CPU slots that hold a classical value.
//!
//! The emitter verifies the stage and runs the address analysis, which fixes
//! the qubit index of most wires. A wire that a `borrow` lends at an index
//! known only at run time gets its qubit index from a register table at run
//! time. A rule that owns a body walks that body once and writes labels and
//! branches around it, so a loop body appears once in the program.

mod engine;
mod error;
mod flow;
mod locals;
mod moves;
mod operand;
mod quantum;
mod rules;
mod source;
mod table;

use kirin::prelude::*;
use kirin_interpreter::dialect::{SemanticKey, SparseForwardShape};

use crate::analysis::address;
use crate::ir::{Squin, query};
use crate::verify::verify;
pub use engine::PpvmEmitter;
pub use error::PpvmError;

/// Name the interpretation that writes ppvm instructions for each statement.
pub struct EmitPpvm;

impl SemanticKey for EmitPpvm {
    type Shape = SparseForwardShape;
}

/// Write the function `function` of the stage `stage` as ppvm `.sst` source text.
pub fn emit(
    pipeline: &Pipeline<StageInfo<Squin>>,
    stage: &str,
    function: &str,
) -> Result<String, PpvmError> {
    let unknown = || PpvmError::UnknownStage(stage.to_string());
    let id = pipeline.stage_by_name(stage).ok_or_else(unknown)?;
    let program = pipeline.stage(id).ok_or_else(unknown)?;
    verify(program).map_err(PpvmError::Invalid)?;
    let addresses = address::analyze(pipeline, stage, function)?;
    let blocks = query::body_blocks(program, addresses.definition());
    let [entry] = blocks[..] else {
        let count = blocks.len();
        return Err(PpvmError::Unsupported(format!(
            "a function body with {count} blocks"
        )));
    };
    let mut emitter = PpvmEmitter::new(program, id, &addresses);
    emitter.block(entry)?;
    Ok(emitter.finish())
}

/// Write the function `function` of the stage `stage` as ppvm `.ssb` bytecode.
///
/// The function writes the `.sst` text first. ppvm's own encoder then
/// resolves its labels and types and packs the instructions.
#[cfg(feature = "ppvm")]
pub fn bytecode(
    pipeline: &Pipeline<StageInfo<Squin>>,
    stage: &str,
    function: &str,
) -> Result<Vec<u8>, PpvmError> {
    let text = emit(pipeline, stage, function)?;
    ppvm_vihaco::bytecode::compile_to_bytes(&text)
        .map_err(|error| PpvmError::Bytecode(format!("{error:#}")))
}
