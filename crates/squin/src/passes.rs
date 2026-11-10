//! Run the squin rewrite rules as passes over one stage of a pipeline.

use kirin::prelude::*;

use crate::language::Squin;
use crate::rewrite::{self, CancelInverse};

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
    pipeline.run_pass::<Squin, _, _, _>(stage, |rewriter| {
        rewrite::apply(rewriter, &[&CancelInverse])
    })
}
