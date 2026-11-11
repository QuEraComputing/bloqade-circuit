use kirin::prelude::*;

use super::{RewriteRule, feeding_gate};
use crate::ir::Squin;
use crate::ir::ops::Gate;

/// Remove two gates in a row that multiply to the identity.
///
/// The rule turns the first program into the second one.
///
/// ```text
/// %a1 = h %a0;
/// %a2 = h %a1;
/// free %a2;
/// ```
///
/// ```text
/// free %a0;
/// ```
///
/// A wire has exactly one use, so the gate that produces the operands of a
/// gate is the previous gate on those qubits.
pub struct CancelInverse;

impl RewriteRule for CancelInverse {
    fn rewrite(
        &self,
        rewriter: &mut Rewriter<'_, Squin>,
        statement: Statement,
    ) -> Result<bool, RewriteError> {
        let stage = rewriter.stage();
        let Some(earlier) = cancelled(stage, statement) else {
            return Ok(false);
        };
        // The gates take no angles, so operand `i` of `earlier` is the wire that
        // result `i` of `statement` continues.
        let outputs: Vec<SSAValue> = statement.results(stage).map(|r| (*r).into()).collect();
        let inputs: Vec<SSAValue> = earlier.arguments(stage).copied().collect();
        for (output, input) in outputs.into_iter().zip(inputs) {
            rewriter.replace_all_uses(output, input)?;
        }
        rewriter.erase_statement(statement)?;
        rewriter.erase_statement(earlier)?;
        Ok(true)
    }
}

/// Return the gate that `statement` cancels.
///
/// That gate multiplies with `statement` to the identity, and `statement` reads
/// all of its results in order.
fn cancelled(stage: &StageInfo<Squin>, statement: Statement) -> Option<Statement> {
    let Squin::Gate(gate) = statement.definition(stage) else {
        return None;
    };
    let operands: Vec<SSAValue> = statement.arguments(stage).copied().collect();
    let (earlier, previous) = feeding_gate(stage, statement, *operands.first()?)?;
    let results: Vec<SSAValue> = earlier.results(stage).map(|r| (*r).into()).collect();
    (is_identity(previous, gate) && operands == results).then_some(earlier)
}

/// Check whether `first` and then `second` on the same qubits are the identity.
fn is_identity(first: &Gate, second: &Gate) -> bool {
    use crate::ir::dialects::gate::Gate::{
        CX, CY, CZ, H, S, SDag, SqrtX, SqrtXDag, SqrtY, SqrtYDag, T, TDag, X, Y, Z,
    };
    matches!(
        (first, second),
        (X(_), X(_))
            | (Y(_), Y(_))
            | (Z(_), Z(_))
            | (H(_), H(_))
            | (CX(_), CX(_))
            | (CY(_), CY(_))
            | (CZ(_), CZ(_))
            | (S(_), SDag(_))
            | (SDag(_), S(_))
            | (T(_), TDag(_))
            | (TDag(_), T(_))
            | (SqrtX(_), SqrtXDag(_))
            | (SqrtXDag(_), SqrtX(_))
            | (SqrtY(_), SqrtYDag(_))
            | (SqrtYDag(_), SqrtY(_))
    )
}
