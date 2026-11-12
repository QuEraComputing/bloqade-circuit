use kirin::prelude::*;
use kirin_arith::{Arith, ArithType};

use super::{RewriteRule, feeding_gate};
use crate::ir::Squin;
use crate::ir::dialects::gate::{Gate, Rx, Ry, Rz};
use crate::ir::types::SquinType;

/// Replace two rotations in a row about one axis by one rotation.
///
/// The rule turns the first program into the second one.
///
/// ```text
/// %a1 = rz(%x) %a0;
/// %a2 = rz(%y) %a1;
/// ```
///
/// ```text
/// %sum = add %x, %y -> f64;
/// %a2 = rz(%sum) %a0;
/// ```
pub struct MergeRotations;

impl RewriteRule for MergeRotations {
    fn rewrite(
        &self,
        rewriter: &mut Rewriter<'_, Squin>,
        statement: Statement,
    ) -> Result<bool, RewriteError> {
        let stage = rewriter.stage();
        let Squin::Gate(gate) = statement.definition(stage) else {
            return Ok(false);
        };
        let mut merged = gate.clone();
        let Some((angle, wire)) = rotation(&mut merged) else {
            return Ok(false);
        };
        let Some((earlier, previous)) = feeding_gate(stage, statement, *wire) else {
            return Ok(false);
        };
        // Two rotations have the same axis if they are the same variant of `Gate`.
        let mut first = previous.clone();
        let same_axis = std::mem::discriminant(gate) == std::mem::discriminant(&first);
        let Some((first_angle, first_wire)) = rotation(&mut first).filter(|_| same_axis) else {
            return Ok(false);
        };
        let result = rewriter.new_result(SquinType::Number(ArithType::F64));
        let sum = Arith::Add {
            lhs: *first_angle,
            rhs: *angle,
            result,
        };
        rewriter.insert_before(statement, Squin::Arith(sum))?;
        (*angle, *wire) = (result.into(), *first_wire);
        rewriter.replace_statement(statement, Squin::Gate(merged))?;
        rewriter.erase_statement(earlier)?;
        Ok(true)
    }
}

/// Return the angle and the input wire of a rotation about one axis.
fn rotation(gate: &mut Gate) -> Option<(&mut SSAValue, &mut SSAValue)> {
    match gate {
        Gate::Rx(Rx { angle, wire, .. })
        | Gate::Ry(Ry { angle, wire, .. })
        | Gate::Rz(Rz { angle, wire, .. }) => Some((angle, wire)),
        _ => None,
    }
}
