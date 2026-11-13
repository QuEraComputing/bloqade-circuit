//! Give each squin statement and each Kirin statement in squin its `EmitPpvm` rule.
//!
//! Each file holds the rules of one dialect. A rule reads the slots of its
//! operands from the engine, writes its instructions, and gives its results
//! slots. The derived `Interpretable` of `Squin` and of the squin wrapper
//! enums dispatches each statement to its rule.

mod classical;
mod control;
mod function;
mod gate;
mod measurement;
mod qubit;
mod register;
mod scf;

use super::PpvmError;

fn unsupported(what: &str) -> PpvmError {
    PpvmError::Unsupported(what.to_string())
}
