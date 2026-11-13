//! Merge the phase rotations of a `circuit` graph that act on the same parity of qubits.
//!
//! The pass follows the idea of phase folding by Amy, Maslov and Mosca. It
//! gives each qubit that enters a run of gates a fresh path variable. An `x`
//! adds the constant 1 to the value of its qubit, and a `cx` adds the value of
//! the control to the target. So the value of each qubit stays a parity: a sum
//! modulo 2 of path variables, maybe with the constant 1 added. Every other
//! gate that changes the value gives its output a fresh variable.
//!
//! A phase gate such as `t` or `rz` multiplies the state by a phase that
//! depends on that parity only. Two phase gates on the same parity therefore
//! merge into one, wherever the parity occurs. The pass puts the merged
//! rotation at the last gate of the group, because every angle value exists
//! there.
//!
//! The pass drops global phases. A statement that consumes a wire, such as
//! `measure`, ends every group.

mod group;
mod parity;
mod rewrite;
mod scan;

use kirin::prelude::*;

use crate::ir::{Squin, query};
use kirin::ir::RewriteError;

/// Merge the phase rotations of every `circuit` graph and return the number
/// of gates that the pass removed.
///
/// The verifier keeps every gate in a graph, so the pass reads the graphs only.
pub fn apply(rewriter: &mut Rewriter<'_, Squin>) -> Result<usize, RewriteError> {
    let mut removed = 0;
    for graph in query::all_graphs(rewriter.stage()) {
        // A graph with a cycle has no gate order, so the pass leaves it alone.
        let Some(nodes) = query::graph_order(rewriter.stage(), graph) else {
            continue;
        };
        for group in scan::groups(rewriter.stage(), &nodes) {
            removed += rewrite::merge(rewriter, group)?;
        }
    }
    Ok(removed)
}
