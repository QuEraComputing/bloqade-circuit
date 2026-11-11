//! Run rewrites as passes over one stage of a pipeline.

mod fold;

use kirin::prelude::*;

use crate::ir::Squin;
use crate::rewrite::rules::{self, CancelInverse, MergeRotations, RewriteRule};

/// Remove each pair of gates in a row that multiplies to the identity.
///
/// The result is the number of pairs that the pass removed.
pub fn cancel_gates<S>(
    pipeline: &mut Pipeline<S>,
    stage: CompileStage,
) -> Result<usize, StagePassError>
where
    S: StageMeta + HasStageInfo<Squin>,
{
    run(pipeline, stage, &[&CancelInverse])
}

/// Replace each run of rotations about one axis by one rotation.
///
/// The result is the number of rotations that the pass removed.
pub fn merge_rotations<S>(
    pipeline: &mut Pipeline<S>,
    stage: CompileStage,
) -> Result<usize, StagePassError>
where
    S: StageMeta + HasStageInfo<Squin>,
{
    run(pipeline, stage, &[&MergeRotations])
}

/// Merge the phase rotations of each block that act on the same parity of qubits.
///
/// The result is the number of gates that the pass removed.
pub fn fold_phases<S>(
    pipeline: &mut Pipeline<S>,
    stage: CompileStage,
) -> Result<usize, StagePassError>
where
    S: StageMeta + HasStageInfo<Squin>,
{
    pipeline.run_pass::<Squin, _, _, _>(stage, fold::apply)
}

/// Run every gate rule until no rule changes the program.
///
/// The result is the number of rewrites.
pub fn simplify<S>(pipeline: &mut Pipeline<S>, stage: CompileStage) -> Result<usize, StagePassError>
where
    S: StageMeta + HasStageInfo<Squin>,
{
    run(pipeline, stage, &[&CancelInverse, &MergeRotations])
}

fn run<S>(
    pipeline: &mut Pipeline<S>,
    stage: CompileStage,
    rules: &[&dyn RewriteRule],
) -> Result<usize, StagePassError>
where
    S: StageMeta + HasStageInfo<Squin>,
{
    pipeline.run_pass::<Squin, _, _, _>(stage, |rewriter| rules::apply(rewriter, rules))
}
