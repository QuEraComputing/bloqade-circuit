//! Run the squin rewrite rules as passes over one stage of a pipeline.

use kirin::prelude::*;

use crate::language::Squin;
use crate::rewrite::{self, CancelInverse, MergeRotations, Rule};

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
    rules: &[&dyn Rule],
) -> Result<usize, StagePassError>
where
    S: StageMeta + HasStageInfo<Squin>,
{
    pipeline.run_pass::<Squin, _, _, _>(stage, |rewriter| rewrite::apply(rewriter, rules))
}
