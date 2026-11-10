use kirin::prelude::*;
use kirin_arith::Arith;

use super::Rule;
use crate::gate::Gate;
use crate::language::Squin;
use crate::types::SquinType;

/// The positions of the operands of a rotation, in the order of its fields.
const ANGLE: usize = 0;
const WIRE: usize = 1;

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
        rewriter.replace_operand(statement, ANGLE, result)?;
        rewriter.replace_operand(statement, WIRE, found.wire)?;
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
}

/// Find the rotation about the same axis that produces the wire of `statement`.
fn earlier_rotation(stage: &StageInfo<Squin>, statement: Statement) -> Option<Earlier> {
    let Squin::Gate(Gate::Rotation {
        axis,
        angle: next_angle,
        wire: input,
        ..
    }) = *statement.definition(stage)
    else {
        return None;
    };
    let SSAKind::Result(earlier, _) = *input.expect_info(stage).kind() else {
        return None;
    };
    let Squin::Gate(Gate::Rotation {
        axis: earlier_axis,
        angle,
        wire,
        ..
    }) = *earlier.definition(stage)
    else {
        return None;
    };
    // A rotation of an outer block can feed both arms of an `if`. The rule keeps
    // that rotation, because the other arm still reads its result.
    let same_block = earlier.parent(stage) == statement.parent(stage);
    (axis == earlier_axis && same_block).then_some(Earlier {
        statement: earlier,
        angle,
        wire,
        next_angle,
    })
}
