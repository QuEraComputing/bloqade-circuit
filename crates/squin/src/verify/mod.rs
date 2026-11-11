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
mod structure;
mod typing;
mod violation;

use kirin::prelude::StageInfo;

use crate::language::Squin;
use program::Program;
pub use structure::{Lending, Nesting, Offset, Structure};
pub use typing::{Typed, Typing};
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
    let mut report = violation::Report::default();
    for root in program.roots() {
        for block in program.blocks(root) {
            for statement in program.body(block) {
                let mut typing = Typing::new(program, &mut report);
                program.definition(statement).check(&mut typing);
            }
            origin::check(program, block, &mut report);
            distinct::check(program, block, &mut report);
        }
        linearity::check(program, root, &mut report);
    }
    report.finish().map(|()| Verified { stage })
}
