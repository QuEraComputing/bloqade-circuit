//! Check that each borrowed qubit returns to the element that it left.

use kirin::prelude::*;
use kirin_scf::StructuredControlFlow;

use super::program::Program;
use super::violation::{Report, Rule};
use crate::language::Squin;
use crate::state::State;
use crate::threads::Threads;

/// Check each `release` and each loop of `block`.
pub(super) fn check(program: Program<'_>, block: Block, report: &mut Report) {
    for statement in program.body(block) {
        match program.definition(statement) {
            Squin::State(State::Release {
                register,
                slot,
                wire,
                ..
            }) => release(program, *register, *slot, *wire, report),
            Squin::Structured(StructuredControlFlow::For(repeat)) => {
                let carried = program.arguments(repeat.body()).skip(1);
                for (argument, result) in carried.zip(program.yields(repeat.body())) {
                    if program.ty(argument).is_linear() && !descends(program, result, argument) {
                        let name = program.name(argument);
                        let message =
                            format!("A loop body moves {name} to another position of its yield.");
                        report.add(Rule::Origin, message);
                    }
                }
            }
            _ => {}
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
        .map(|(statement, _)| program.definition(statement));
    let Some(Squin::State(State::Borrow {
        register_out: lender,
        wire: lent,
        ..
    })) = borrow
    else {
        return;
    };
    if !descends(program, wire, (*lent).into()) {
        let (wire, slot) = (program.name(wire), program.name(slot));
        let message = format!("{wire} fills {slot}, and it carries another qubit.");
        report.add(Rule::Origin, message);
    }
    if !descends(program, register, (*lender).into()) {
        let (register, slot) = (program.name(register), program.name(slot));
        let message = format!("{slot} names an element of another register than {register}.");
        report.add(Rule::Origin, message);
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
fn previous(program: Program<'_>, value: SSAValue) -> Option<SSAValue> {
    let (statement, index) = program.producer(value)?;
    match program.definition(statement) {
        Squin::Structured(StructuredControlFlow::If(branch)) => {
            let then = entering(program, branch.then_block(), index)?;
            let other = entering(program, branch.else_block(), index)?;
            (then == other).then_some(then)
        }
        Squin::Structured(StructuredControlFlow::For(repeat)) => {
            repeat.init_args().get(index).copied()
        }
        definition => {
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
