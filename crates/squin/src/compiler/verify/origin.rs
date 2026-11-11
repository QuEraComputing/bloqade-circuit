//! Check that each borrowed qubit returns to the element that it left.

use kirin::prelude::*;

use super::program::Program;
use super::violation::{Report, Violation};
use crate::dialect::traits::{Lending, Nesting, Structure, Threads};

/// Check each `release` and each loop of `block`.
pub(super) fn check(program: Program<'_>, block: Block, report: &mut Report) {
    for statement in program.body(block) {
        let definition = program.definition(statement);
        if let Some(Lending::Release {
            register,
            slot,
            wire,
        }) = definition.lending()
        {
            release(program, register, slot, wire, report);
        }
        if let Nesting::Loop { body, .. } = definition.nesting() {
            let carried = program.arguments(body).skip(1);
            for (argument, result) in carried.zip(program.yields(body)) {
                if program.ty(argument).is_linear() && !descends(program, result, argument) {
                    let value = program.named(argument);
                    report.add(Violation::LoopMoves { value });
                }
            }
        }
    }
}

/// Check that a `release` fills its slot with the qubit that left it.
fn release(
    program: Program<'_>,
    register: SSAValue,
    slot: SSAValue,
    wire: SSAValue,
    report: &mut Report,
) {
    let borrow = program
        .producer(slot)
        .and_then(|(statement, _)| program.definition(statement).lending());
    let Some(Lending::Borrow {
        register_out: lender,
        wire: lent,
        ..
    }) = borrow
    else {
        return;
    };
    if !descends(program, wire, lent.into()) {
        let (wire, slot) = (program.named(wire), program.named(slot));
        report.add(Violation::WrongQubit { wire, slot });
    }
    if !descends(program, register, lender.into()) {
        let (slot, register) = (program.named(slot), program.named(register));
        report.add(Violation::WrongRegister { slot, register });
    }
}

/// Check whether `value` names the same qubit or register as `ancestor`.
fn descends(program: Program<'_>, mut value: SSAValue, ancestor: SSAValue) -> bool {
    while value != ancestor {
        match previous(program, value) {
            Some(earlier) => value = earlier,
            None => return false,
        }
    }
    true
}

/// Return the value that `value` continues, one statement earlier.
///
/// A result of an `if` continues a value if both arms yield that value at the
/// same position. A result of a loop continues the initial value at its position.
pub(super) fn previous(program: Program<'_>, value: SSAValue) -> Option<SSAValue> {
    let (statement, index) = program.producer(value)?;
    let definition = program.definition(statement);
    match definition.nesting() {
        Nesting::Arms([then, other]) => {
            let then = entering(program, then, index)?;
            let other = entering(program, other, index)?;
            (then == other).then_some(then)
        }
        Nesting::Loop { initial, .. } => initial.get(index).copied(),
        Nesting::Flat => {
            let threads = definition.threads();
            let pair = threads.iter().find(|(_, result)| value == (*result).into());
            pair.map(|(operand, _)| *operand)
        }
    }
}

/// Return the outer value that `block` yields at position `index`.
fn entering(program: Program<'_>, block: Block, index: usize) -> Option<SSAValue> {
    let mut value = *program.yields(block).get(index)?;
    while program.home(value) == Some(block) {
        value = previous(program, value)?;
    }
    Some(value)
}
