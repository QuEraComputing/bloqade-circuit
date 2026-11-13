//! Replace each phase group with gates that apply its total rotation.

use kirin::prelude::*;
use kirin_arith::Arith;
use kirin_arith::ArithType;

use super::group::{Group, Phase};
use crate::ir::Squin;
use crate::ir::dialects::gate::{Gate, Rz, S, SDag, T, TDag, Z};
use crate::ir::traits::Threads;
use crate::ir::types::SquinType;
use crate::rewrite::insert_near;

/// Return the input wire and the output wire of the one-qubit gate `statement`.
fn wires(stage: &StageInfo<Squin>, statement: Statement) -> (SSAValue, ResultValue) {
    match statement.definition(stage) {
        Squin::Gate(gate) => gate.threads()[0],
        _ => unreachable!("a group holds phase gates only"),
    }
}

/// Build a one-qubit gate on `wire` with the output `wire_out`.
type Make = fn(SSAValue, ResultValue) -> Gate;

const Z_GATE: Make = |wire, wire_out| Gate::Z(Z { wire, wire_out });
const S_GATE: Make = |wire, wire_out| Gate::S(S { wire, wire_out });
const S_DAG_GATE: Make = |wire, wire_out| Gate::SDag(SDag { wire, wire_out });
const T_GATE: Make = |wire, wire_out| Gate::T(T { wire, wire_out });
const T_DAG_GATE: Make = |wire, wire_out| Gate::TDag(TDag { wire, wire_out });

/// Return the fewest fixed gates whose phase is `eighths` eighths of a turn.
fn fixed(eighths: i64) -> &'static [Make] {
    match eighths.rem_euclid(8) {
        1 => &[T_GATE],
        2 => &[S_GATE],
        3 => &[S_GATE, T_GATE],
        4 => &[Z_GATE],
        5 => &[Z_GATE, T_GATE],
        6 => &[S_DAG_GATE],
        7 => &[T_DAG_GATE],
        _ => &[],
    }
}

/// Replace the gates of `group` by the merged rotation and return the number
/// of gates that the replacement removed.
///
/// The group stays as it is if the replacement has as many gates.
pub(super) fn merge(
    rewriter: &mut Rewriter<'_, Squin>,
    group: Group,
) -> Result<usize, RewriteError> {
    let Some(anchor) = group.occurrences.last() else {
        return Ok(0);
    };
    let anchor = (anchor.statement, anchor.negated);
    let mut eighths = 0;
    let mut angles = Vec::new();
    if !group.constant {
        for occurrence in &group.occurrences {
            let negative = occurrence.negated != anchor.1;
            match occurrence.phase {
                Phase::Eighths(value) => eighths += if negative { -value } else { value },
                Phase::Angle(angle) => angles.push((angle, negative)),
            }
        }
    }
    let gates = fixed(eighths);
    let emitted = gates.len() + usize::from(!angles.is_empty());
    if emitted >= group.occurrences.len() {
        return Ok(0);
    }

    let (others, _) = group.occurrences.split_at(group.occurrences.len() - 1);
    for other in others {
        let (input, output) = wires(rewriter.stage(), other.statement);
        rewriter.replace_all_uses(output, input)?;
        rewriter.erase_statement(other.statement)?;
    }
    let (mut wire, output) = wires(rewriter.stage(), anchor.0);
    for make in gates {
        wire = place(rewriter, anchor.0, wire, *make)?;
    }
    if let Some(angle) = total(rewriter, anchor.0, &angles)? {
        wire = place(rewriter, anchor.0, wire, |wire, wire_out| {
            Gate::Rz(Rz {
                angle,
                wire,
                wire_out,
            })
        })?;
    }
    rewriter.replace_all_uses(output, wire)?;
    rewriter.erase_statement(anchor.0)?;
    Ok(group.occurrences.len() - emitted)
}

/// Insert the gate that `make` builds on `wire` before `anchor`, and return its output wire.
fn place(
    rewriter: &mut Rewriter<'_, Squin>,
    anchor: Statement,
    wire: SSAValue,
    make: impl FnOnce(SSAValue, ResultValue) -> Gate,
) -> Result<SSAValue, RewriteError> {
    let output = rewriter.new_result(SquinType::Wire);
    insert_near(rewriter, anchor, Squin::Gate(make(wire, output)))?;
    Ok(output.into())
}

/// Insert the sum of `angles` before `anchor` and return it.
///
/// Each angle has a flag that is true if the sum subtracts it. The result is
/// `None` if `angles` is empty.
fn total(
    rewriter: &mut Rewriter<'_, Squin>,
    anchor: Statement,
    angles: &[(SSAValue, bool)],
) -> Result<Option<SSAValue>, RewriteError> {
    let mut sum: Option<SSAValue> = None;
    for &(angle, negative) in angles {
        let term = if negative {
            let result = rewriter.new_result(SquinType::Number(ArithType::F64));
            let negated = Arith::Neg {
                operand: angle,
                result,
            };
            insert_near(rewriter, anchor, Squin::Arith(negated))?;
            result.into()
        } else {
            angle
        };
        sum = Some(match sum {
            None => term,
            Some(lhs) => {
                let result = rewriter.new_result(SquinType::Number(ArithType::F64));
                let added = Arith::Add {
                    lhs,
                    rhs: term,
                    result,
                };
                insert_near(rewriter, anchor, Squin::Arith(added))?;
                result.into()
            }
        });
    }
    Ok(sum)
}
