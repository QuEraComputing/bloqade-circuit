//! Check the linear rules of a squin program.
//!
//! The rules are local. Each one reads a single block, or follows the `Threads`
//! pairs from one statement to the statement before it. A rule asks each
//! statement for its facts through the traits `Typed` and `Structure`, which
//! this module owns, and through `Threads` of the IR.

mod distinct;
mod linearity;
mod origin;
mod program;
mod scope;
mod structure;
mod type_check;
mod typing;
mod typing_context;
mod violation;

use kirin::prelude::StageInfo;

use crate::ir::Squin;
use program::Program;
pub use structure::{Lending, Nesting, Offset, Structure};
pub use type_check::TypeCheck;
pub use typing::Typed;
use typing_context::Typing;
pub use violation::{Named, Rule, Violation};

/// Check every function of `stage` and return each violation of a rule.
pub fn verify(stage: &StageInfo<Squin>) -> Result<(), Vec<Violation>> {
    let program = Program::new(stage);
    let mut scopes = violation::Report::default();
    for function in program.functions() {
        for root in program.roots(function) {
            scope::check(program, root, &mut scopes);
        }
    }
    scopes.finish()?;
    let mut report = violation::Report::default();
    for function in program.functions() {
        program
            .definition(function)
            .check(&mut Typing::new(program, &mut report));
        for root in program.roots(function) {
            for block in program.blocks(root) {
                for value in program.definitions(block) {
                    Typing::new(program, &mut report).validate_type(value);
                }
                for statement in program.body(block) {
                    let mut typing = Typing::new(program, &mut report);
                    program.definition(statement).check(&mut typing);
                }
                origin::check(program, block, &mut report);
                distinct::check(program, block, &mut report);
            }
            linearity::check(program, root, &mut report);
        }
    }
    report.finish()
}
