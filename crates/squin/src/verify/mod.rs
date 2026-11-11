//! Check the linear rules of a squin program.
//!
//! The rules are local. Each one reads a single block, or follows the `Threads`
//! pairs from one statement to the statement before it.

mod distinct;
mod linearity;
mod origin;
mod program;
mod typing;
mod violation;

use kirin::prelude::StageInfo;

use crate::language::Squin;
use program::Program;
pub use violation::{Rule, Violation};

/// Check every function of `stage` and return each violation of a rule.
pub fn verify(stage: &StageInfo<Squin>) -> Result<(), Vec<Violation>> {
    let program = Program::new(stage);
    let mut report = violation::Report::default();
    for root in program.roots() {
        for block in program.blocks(root) {
            for statement in program.body(block) {
                typing::check(program, statement, &mut report);
            }
            origin::check(program, block, &mut report);
            distinct::check(program, block, &mut report);
        }
        linearity::check(program, root, &mut report);
    }
    report.finish()
}
