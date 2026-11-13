//! Rewrite squin programs.
//!
//! `rules` holds the local rules as Kirin `#[rewrite_rule]` patterns.
//! `passes` runs those rules with Kirin's `RewriteDriver`, and it runs the
//! phase folding of whole circuit graphs.

pub mod passes;
pub mod rules;

use kirin::prelude::*;

use crate::ir::Squin;

/// Insert `definition` next to `anchor` and return the new statement.
///
/// In a block, the new statement goes right before `anchor`. In a graph, the
/// node order carries no meaning, so the new statement becomes a node.
pub(crate) fn insert_near(
    rewriter: &mut Rewriter<'_, Squin>,
    anchor: Statement,
    definition: Squin,
) -> Result<Statement, RewriteError> {
    match *anchor.parent(rewriter.stage()) {
        Some(StatementParent::DiGraph(graph)) => rewriter.insert_node(graph, definition),
        _ => rewriter.insert_before(anchor, definition),
    }
}
