use kirin::prelude::*;

use super::Rule;
use crate::ir::Squin;
use crate::ir::dialects::gate::Gate;
use crate::ir::traits::Threads;

/// Remove two gates in a row that multiply to the identity.
///
/// The rule turns the first program into the second one.
///
/// ```text
/// %a1 = h %a0 -> Wire;
/// %a2 = h %a1 -> Wire;
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

impl Rule for CancelInverse {
    fn rewrite(
        &self,
        rewriter: &mut Rewriter<'_, Squin>,
        statement: Statement,
    ) -> Result<bool, RewriteError> {
        let Some((earlier, wires)) = cancelled(rewriter.stage(), statement) else {
            return Ok(false);
        };
        for (result, input) in wires {
            rewriter.replace_all_uses(result, input)?;
        }
        rewriter.erase_statement(statement)?;
        rewriter.erase_statement(earlier)?;
        Ok(true)
    }
}

/// Find the gate that `statement` cancels.
///
/// The result holds that earlier gate. It also pairs each result of `statement`
/// with the wire that the earlier gate received for the same qubit.
fn cancelled(
    stage: &StageInfo<Squin>,
    statement: Statement,
) -> Option<(Statement, Vec<(ResultValue, SSAValue)>)> {
    let Squin::Gate(gate) = statement.definition(stage) else {
        return None;
    };
    let threads = gate.threads();
    let (first, _) = threads.first()?;
    let SSAKind::Result(earlier, _) = *first.expect_info(stage).kind() else {
        return None;
    };
    let Squin::Gate(previous) = earlier.definition(stage) else {
        return None;
    };
    // A gate of an outer block can feed both arms of an `if`. The rule keeps
    // that gate, because the other arm still reads its result.
    if !is_identity(previous, gate) || earlier.parent(stage) != statement.parent(stage) {
        return None;
    }
    let inputs = previous.threads();
    let same_qubits = inputs.len() == threads.len()
        && inputs
            .iter()
            .zip(&threads)
            .all(|((_, passed), (operand, _))| *operand == (*passed).into());
    let wires = inputs.iter().zip(&threads);
    same_qubits.then(|| {
        (
            earlier,
            wires
                .map(|((input, _), (_, result))| (*result, *input))
                .collect(),
        )
    })
}

/// Check whether `first` and then `second` on the same qubits are the identity.
fn is_identity(first: &Gate, second: &Gate) -> bool {
    use Gate::{CX, CY, CZ, H, S, SDag, SqrtX, SqrtXDag, SqrtY, SqrtYDag, T, TDag, X, Y, Z};
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
