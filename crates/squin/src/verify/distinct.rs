//! Check that two open borrows of one register use distinct elements.

use std::collections::HashMap;

use kirin::prelude::*;

use super::origin::previous;
use super::program::Program;
use super::structure::{Lending, Offset, Structure};
use super::violation::{Report, Violation};
use crate::ir::types::SquinType;

/// Describe an index as a constant offset from a base value.
///
/// `base` is `None` for a constant. For example, `add %k, %one` has the base
/// `%k` and the offset 1 if `%one` is the constant 1.
#[derive(Clone, Copy, PartialEq, Eq)]
struct Index {
    base: Option<SSAValue>,
    offset: i64,
}

impl Index {
    /// Check that the two indices differ in every execution.
    ///
    /// Two indices with one base and two offsets always differ. The check
    /// cannot compare two indices with different bases.
    fn differs_from(self, other: Index) -> bool {
        self.base == other.base && self.offset != other.offset
    }
}

/// Check each `borrow` of `block` against the open borrows of its register.
pub(super) fn check(program: Program<'_>, block: Block, report: &mut Report) {
    let mut indices = HashMap::new();
    for statement in program.body(block) {
        let Some(Lending::Borrow {
            register, index, ..
        }) = program.definition(statement).lending()
        else {
            continue;
        };
        let Some(open) = open_borrows(program, register) else {
            report.add(Violation::UnknownBorrows {
                register: program.named(register),
            });
            continue;
        };
        for open in open {
            if !index_of(program, index, &mut indices).differs_from(index_of(
                program,
                open,
                &mut indices,
            )) {
                let (first, second) = (program.named(open), program.named(index));
                report.add(Violation::SameElement { first, second });
            }
        }
    }
}

/// Return the indices of the open borrows of `register`.
///
/// The walk follows loop arguments to their initial values.
/// If the walk cannot find every open borrow, return `None`.
fn open_borrows(program: Program<'_>, mut register: SSAValue) -> Option<Vec<SSAValue>> {
    let mut released = Vec::new();
    let mut open = Vec::new();
    while matches!(program.ty(register), SquinType::Register { lent, .. } if lent > 0) {
        let Some((statement, _)) = program.producer(register) else {
            register = program.loop_initial(register)?;
            continue;
        };
        match program.definition(statement).lending() {
            Some(Lending::Release { slot, .. }) => released.push(slot),
            Some(Lending::Borrow { slot, index, .. }) if !released.contains(&slot.into()) => {
                open.push(index);
            }
            _ => {}
        }
        register = previous(program, register)?;
    }
    Some(open)
}

/// Read `value` as a constant offset and cache each expression that the walk visits.
fn index_of(
    program: Program<'_>,
    value: SSAValue,
    indices: &mut HashMap<SSAValue, Index>,
) -> Index {
    let mut pending = vec![value];
    while let Some(current) = pending.pop() {
        if indices.contains_key(&current) {
            continue;
        }
        let opaque = Index {
            base: Some(current),
            offset: 0,
        };
        let expression = program
            .producer(current)
            .and_then(|(statement, _)| program.definition(statement).offset());
        let computed = match expression {
            Some(Offset::Constant(offset)) => Some(Index { base: None, offset }),
            Some(Offset::Sum(lhs, rhs) | Offset::Difference(lhs, rhs)) => {
                let (Some(left), Some(right)) = (indices.get(&lhs), indices.get(&rhs)) else {
                    pending.push(current);
                    if !indices.contains_key(&rhs) {
                        pending.push(rhs);
                    }
                    if !indices.contains_key(&lhs) {
                        pending.push(lhs);
                    }
                    continue;
                };
                match expression {
                    Some(Offset::Sum(..)) => match (left.base, right.base) {
                        (base, None) | (None, base) => left
                            .offset
                            .checked_add(right.offset)
                            .map(|offset| Index { base, offset }),
                        _ => None,
                    },
                    _ => left
                        .offset
                        .checked_sub(right.offset)
                        .filter(|_| right.base.is_none())
                        .map(|offset| Index {
                            base: left.base,
                            offset,
                        }),
                }
            }
            None => None,
        };
        indices.insert(current, computed.unwrap_or(opaque));
    }
    indices[&value]
}
