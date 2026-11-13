//! Write a squin function as a Stim circuit.
//!
//! The emitter verifies the stage and runs the address analysis. It then walks
//! the function in program order. Each wire must carry a known qubit, so the
//! function needs constant register sizes and constant indices. Stim has no
//! loops over squin values and no branches, so a `for` and a `repeat` are
//! errors, and an `if` or a `conditional` needs a condition that the analysis
//! knows. A `circuit` region emits its graph in dependency order.
//!
//! The emitter gives each qubit a Stim index. A qubit after a `free` gives its
//! index to the next allocation, which resets it first.

mod error;
mod names;
mod writer;

use kirin::prelude::*;

use crate::analysis::address;
use crate::ir::{Squin, query};
use crate::verify::verify;
pub use error::StimError;
use writer::Writer;

/// Write the function `function` of the stage `stage` as a Stim circuit.
///
/// The result holds one instruction on each line.
pub fn emit(
    pipeline: &Pipeline<StageInfo<Squin>>,
    stage: &str,
    function: &str,
) -> Result<String, StimError> {
    let unknown = || StimError::UnknownStage(stage.to_string());
    let program = pipeline.stage(pipeline.stage_by_name(stage).ok_or_else(unknown)?);
    let program = program.ok_or_else(unknown)?;
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
    let mut writer = Writer::new(program, &addresses);
    writer.block(entry)?;
    Ok(writer.finish())
}
