use kirin::prelude::*;

use super::Rule;
use crate::language::Squin;
use crate::threads::Threads;

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
    if !previous.cancels(gate) || earlier.parent(stage) != statement.parent(stage) {
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
