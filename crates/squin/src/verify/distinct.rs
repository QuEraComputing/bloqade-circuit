//! Check that two open borrows of one register use distinct elements.

use kirin::prelude::*;

use super::origin::previous;
use super::program::Program;
use super::structure::{Lending, Offset, Structure};
use super::violation::{Report, Violation};
use crate::types::SquinType;

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
    for statement in program.body(block) {
        let Some(Lending::Borrow {
            register, index, ..
        }) = program.definition(statement).lending()
        else {
            continue;
        };
        for open in open_borrows(program, register) {
            if !index_of(program, index).differs_from(index_of(program, open)) {
                let (first, second) = (program.named(open), program.named(index));
                report.add(Violation::SameElement { first, second });
            }
        }
    }
}

/// Return the index of each `borrow` that lent an element of `register` and
/// that no `release` has filled.
///
/// The walk follows the register back from statement to statement. It stops at
/// the first value that has every element in place.
fn open_borrows(program: Program<'_>, mut register: SSAValue) -> Vec<SSAValue> {
    let mut released = Vec::new();
    let mut open = Vec::new();
    while matches!(program.ty(register), SquinType::Register { lent, .. } if lent > 0) {
        let Some((statement, _)) = program.producer(register) else {
            break;
        };
        match program.definition(statement).lending() {
            Some(Lending::Release { slot, .. }) => released.push(slot),
            Some(Lending::Borrow { slot, index, .. }) if !released.contains(&slot.into()) => {
                open.push(index);
            }
            _ => {}
        }
        let Some(earlier) = previous(program, register) else {
            break;
        };
        register = earlier;
    }
    open
}

/// Read `value` as a constant offset from a base value.
fn index_of(program: Program<'_>, value: SSAValue) -> Index {
    let opaque = Index {
        base: Some(value),
        offset: 0,
    };
    let Some((statement, _)) = program.producer(value) else {
        return opaque;
    };
    let shifted = match program.definition(statement).offset() {
        Some(Offset::Constant(offset)) => Some(Index { base: None, offset }),
        Some(Offset::Sum(lhs, rhs)) => {
            let (left, right) = (index_of(program, lhs), index_of(program, rhs));
            match (left.base, right.base) {
                (base, None) | (None, base) => {
                    let offset = left.offset.checked_add(right.offset);
                    offset.map(|offset| Index { base, offset })
                }
                _ => None,
            }
        }
        Some(Offset::Difference(lhs, rhs)) => {
            let (left, right) = (index_of(program, lhs), index_of(program, rhs));
            let offset = left.offset.checked_sub(right.offset);
            let base = left.base;
            offset
                .filter(|_| right.base.is_none())
                .map(|offset| Index { base, offset })
        }
        None => None,
    };
    shifted.unwrap_or(opaque)
}
