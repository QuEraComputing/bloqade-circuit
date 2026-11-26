use crate::rewrite::{merge_rz, remove_zero_rz, rz_at};
use crate::{Type, ops::Rz};
use kirin::prelude::*;
use std::collections::VecDeque;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct RzStats {
    pub removed_zero: usize,
    pub merged: usize,
}

/// The caller supplies a valid Squin stage.
pub fn optimize_rz<L, S>(
    pipeline: &mut Pipeline<S>,
    stage: CompileStage,
) -> Result<RzStats, StagePassError>
where
    S: StageMeta + HasStageInfo<L>,
    L: Dialect<Type = Type> + TryProjectTo<Rz> + From<Rz>,
{
    pipeline.run_pass::<L, _, _, _>(stage, rewrite_rz)
}

fn rewrite_rz<L>(rw: &mut Rewriter<L>) -> Result<RzStats, RewriteError>
where
    L: Dialect<Type = Type> + TryProjectTo<Rz> + From<Rz>,
{
    let mut pending: VecDeque<_> = rw
        .stage()
        .digraph_arena()
        .iter()
        .flat_map(|graph| graph.graph().node_weights().copied())
        .collect();
    let mut stats = RzStats::default();
    while let Some(statement) = pending.pop_front() {
        let Some(op) = rz_at(rw.stage(), statement) else {
            continue;
        };
        let users: Vec<_> = op
            .wire_out
            .expect_info(rw.stage())
            .uses()
            .iter()
            .filter_map(|usage| match usage {
                Use::StatementOperand { stmt, .. } => Some(*stmt),
                Use::DiGraphYield { .. } => None,
            })
            .collect();
        if remove_zero_rz(rw, statement)? {
            stats.removed_zero += 1;
        } else if merge_rz(rw, statement)? {
            stats.merged += 1;
            pending.push_front(statement);
        } else {
            continue;
        }
        pending.extend(users);
    }
    Ok(stats)
}
