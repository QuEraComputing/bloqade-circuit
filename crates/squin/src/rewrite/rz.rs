use crate::{Type, ops::Rz};
use kirin::prelude::*;

pub(crate) fn rz_at<L>(stage: &StageInfo<L>, statement: Statement) -> Option<Rz>
where
    L: Dialect + TryProjectTo<Rz>,
{
    statement
        .get_info(stage)?
        .definition()
        .clone()
        .try_project_to()
        .ok()
}

/// Call this rule on a stage that passes Squin validation.
pub fn remove_zero_rz<L>(rw: &mut Rewriter<L>, statement: Statement) -> Result<bool, RewriteError>
where
    L: Dialect<Type = Type> + TryProjectTo<Rz>,
{
    let Some(op) = rz_at(rw.stage(), statement) else {
        return Ok(false);
    };
    if op.angle != 0.0 {
        return Ok(false);
    }
    rw.replace_all_uses(op.wire_out, op.wire)?;
    rw.erase_statement(statement)?;
    Ok(true)
}

/// Call this rule on a stage that passes Squin validation.
pub fn merge_rz<L>(rw: &mut Rewriter<L>, statement: Statement) -> Result<bool, RewriteError>
where
    L: Dialect<Type = Type> + TryProjectTo<Rz> + From<Rz>,
{
    let Some(second) = rz_at(rw.stage(), statement) else {
        return Ok(false);
    };
    let input = second.wire.expect_info(rw.stage());
    let SSAKind::Result(predecessor, _) = *input.kind() else {
        return Ok(false);
    };
    let Some(first) = rz_at(rw.stage(), predecessor) else {
        return Ok(false);
    };
    rw.replace_statement(
        statement,
        Rz {
            angle: first.angle + second.angle,
            wire: first.wire,
            wire_out: second.wire_out,
        }
        .into(),
    )?;
    rw.erase_statement(predecessor)?;
    Ok(true)
}
