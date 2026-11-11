//! Define local rewrite rules and the driver that applies them.
//!
//! A [`RewriteRule`] looks at one statement and edits the program around it. [`apply`]
//! offers each statement to each rule until no rule changes the program.

mod cancel;
mod merge;

use kirin::ir::walk::{KeepOrderReverseBFS, WalkCursor, WalkError, WalkOrder};
use kirin::prelude::*;

use crate::ir::{Squin, query};
pub use cancel::CancelInverse;
pub use merge::MergeRotations;

/// Rewrite the program around one statement.
pub trait RewriteRule {
    /// Try to rewrite `statement` and return whether the program changed.
    ///
    /// A failed pass keeps the edits that it made. A rule therefore checks
    /// every condition of a rewrite before its first edit.
    fn rewrite(
        &self,
        rewriter: &mut Rewriter<'_, Squin>,
        statement: Statement,
    ) -> Result<bool, RewriteError>;
}

/// Apply `rules` to every function until no rule changes the program.
///
/// The result is the number of rewrites. Each sweep fixes its visit order at
/// its start, so a rule can erase the statement that it visits.
pub fn apply(
    rewriter: &mut Rewriter<'_, Squin>,
    rules: &[&dyn RewriteRule],
) -> Result<usize, RuleError> {
    let mut rewrites = 0;
    loop {
        let before = rewrites;
        for root in query::functions(rewriter.stage()) {
            let mut cursor = KeepOrderReverseBFS::start(rewriter.stage(), root);
            while let Some(statement) = cursor.next(rewriter.stage())? {
                for rule in rules {
                    if statement.get_info(rewriter.stage()).is_none() {
                        break;
                    }
                    if rule.rewrite(rewriter, statement)? {
                        rewrites += 1;
                    }
                }
            }
        }
        if rewrites == before {
            return Ok(rewrites);
        }
    }
}

/// Tell why a pass over the rules stopped before its end.
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum RuleError {
    /// The rewriter rejected an edit of a rule.
    #[error("A rule made an edit that the rewriter rejects.")]
    Rewrite(#[from] RewriteError),
    /// A rule made an edit that the visit order forbids.
    #[error("A rule broke the visit order of its pass.")]
    Walk(#[from] WalkError),
}
