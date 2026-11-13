//! Write a squin function as a program for ppvm, QuEra's circuit simulator.
//!
//! ppvm runs programs on vihaco, a stack machine with a `cpu` component for
//! classical work and a `circuit` component for quantum instructions. The
//! emitter writes `.sst` source text, and the `ppvm` feature turns that text
//! into `.ssb` bytecode through `ppvm_vihaco`. The emitter runs nothing.
//!
//! The emitter verifies the stage and runs the address analysis, which fixes
//! the qubit index of each wire. It then walks the function in program order
//! and each `circuit` graph in dependency order. A `conditional`, an `if`, a
//! `repeat` and a `for` become labels and branches of the CPU, so the program
//! can branch on a measurement. Each classical value lives in a local slot.

mod classical;
mod control;
mod error;
mod locals;
mod moves;
mod names;
mod writer;

use kirin::prelude::*;

use crate::analysis::address;
use crate::ir::{Squin, query};
use crate::verify::verify;
pub use error::PpvmError;
use writer::Writer;

/// Write the function `function` of the stage `stage` as ppvm `.sst` source text.
pub fn emit(
    pipeline: &Pipeline<StageInfo<Squin>>,
    stage: &str,
    function: &str,
) -> Result<String, PpvmError> {
    let unknown = || PpvmError::UnknownStage(stage.to_string());
    let program = pipeline.stage(pipeline.stage_by_name(stage).ok_or_else(unknown)?);
    let program = program.ok_or_else(unknown)?;
    verify(program).map_err(PpvmError::Invalid)?;
    let addresses = address::analyze(pipeline, stage, function)?;
    let blocks = query::body_blocks(program, addresses.definition());
    let [entry] = blocks[..] else {
        let count = blocks.len();
        return Err(PpvmError::Unsupported(format!(
            "a function body with {count} blocks"
        )));
    };
    let mut writer = Writer::new(program, &addresses);
    writer.block(entry)?;
    Ok(writer.finish())
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
