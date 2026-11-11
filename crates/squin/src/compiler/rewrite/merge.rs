use kirin::prelude::*;
use kirin_arith::Arith;

use super::Rule;
use crate::dialect::Squin;
use crate::dialect::gate::{Gate, Rx, Ry, Rz};
use crate::dialect::types::SquinType;

/// Replace two rotations in a row about one axis by one rotation.
///
/// The rule turns the first program into the second one.
///
/// ```text
/// %a1 = rz(%x) %a0 -> Wire;
/// %a2 = rz(%y) %a1 -> Wire;
/// ```
///
/// ```text
/// %sum = add %x, %y -> Float;
/// %a2 = rz(%sum) %a0 -> Wire;
/// ```
pub struct MergeRotations;

impl Rule for MergeRotations {
    fn rewrite(
        &self,
        rewriter: &mut Rewriter<'_, Squin>,
        statement: Statement,
    ) -> Result<bool, RewriteError> {
        let Some(found) = earlier_rotation(rewriter.stage(), statement) else {
            return Ok(false);
        };
        let result = rewriter.new_result(SquinType::Float);
        let (lhs, rhs) = (found.angle, found.next_angle);
        let sum = Arith::Add { lhs, rhs, result };
        rewriter.insert_before(statement, Squin::Arith(sum))?;
        for (old, new) in [(found.next_angle, result.into()), (found.input, found.wire)] {
            let operands = statement.arguments(rewriter.stage());
            let index = operands.into_iter().position(|operand| *operand == old);
            let index = index.ok_or(RewriteError::UnknownValue(old))?;
            rewriter.replace_operand(statement, index, new)?;
        }
        rewriter.erase_statement(found.statement)?;
        Ok(true)
    }
}

/// Hold the rotation that comes before another rotation on the same qubit.
struct Earlier {
    statement: Statement,
    angle: SSAValue,
    wire: SSAValue,
    /// The angle of the rotation that comes after `statement`.
    next_angle: SSAValue,
    /// The wire that the later rotation reads, which `statement` produces.
    input: SSAValue,
}

/// Find the rotation about the same axis that produces the wire of `statement`.
fn earlier_rotation(stage: &StageInfo<Squin>, statement: Statement) -> Option<Earlier> {
    let Squin::Gate(gate) = statement.definition(stage) else {
        return None;
    };
    let (next_angle, input) = rotation(gate)?;
    let SSAKind::Result(earlier, _) = *input.expect_info(stage).kind() else {
        return None;
    };
    let Squin::Gate(earlier_gate) = earlier.definition(stage) else {
        return None;
    };
    let (angle, wire) = rotation(earlier_gate)?;
    // Two gates have the same axis if they are the same variant of `Gate`.
    let same_axis = std::mem::discriminant(gate) == std::mem::discriminant(earlier_gate);
    // A rotation of an outer block can feed both arms of an `if`. The rule keeps
    // that rotation, because the other arm still reads its result.
    let same_block = earlier.parent(stage) == statement.parent(stage);
    (same_axis && same_block).then_some(Earlier {
        statement: earlier,
        angle,
        wire,
        next_angle,
        input,
    })
}

/// Return the angle and the input wire of a rotation about one axis.
fn rotation(gate: &Gate) -> Option<(SSAValue, SSAValue)> {
    match gate {
        Gate::Rx(Rx { angle, wire, .. })
        | Gate::Ry(Ry { angle, wire, .. })
        | Gate::Rz(Rz { angle, wire, .. }) => Some((*angle, *wire)),
        _ => None,
    }
}
