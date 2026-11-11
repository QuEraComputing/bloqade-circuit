//! Check the linear rules of a squin program.
//!
//! The rules are local. Each one reads a single block, or follows the `Threads`
//! pairs from one statement to the statement before it. A rule asks each
//! statement for its facts through the traits `Typed`, `Structure` and
//! `Threads`, so a new statement brings its own rules.

mod distinct;
mod linearity;
mod origin;
mod program;
mod scope;
mod typing;
mod violation;

use kirin::prelude::StageInfo;

use crate::ir::Squin;
use program::Program;
use typing::Typing;
pub use typing::{TypeCheck, Typed};
pub use violation::{Named, Rule, Violation};

/// Prove that a stage passes every verifier rule.
///
/// `verify` is the one public way to get this value. The evaluator requires it,
/// so it runs verified programs only.
#[derive(Clone, Copy)]
pub struct Verified<'a> {
    stage: &'a StageInfo<Squin>,
}

impl<'a> Verified<'a> {
    /// Return the stage that passed the rules.
    pub fn stage(self) -> &'a StageInfo<Squin> {
        self.stage
    }

    /// Wrap a stage that the caller has verified since its last change.
    pub(crate) fn trusted(stage: &'a StageInfo<Squin>) -> Self {
        Self { stage }
    }
}

/// Check every function of `stage` and return each violation of a rule.
pub fn verify(stage: &StageInfo<Squin>) -> Result<Verified<'_>, Vec<Violation>> {
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
    report.finish().map(|()| Verified { stage })
}
