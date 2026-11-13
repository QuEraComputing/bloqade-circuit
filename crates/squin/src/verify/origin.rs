//! Check that each borrowed qubit returns to the element that it left.

use kirin::prelude::*;

use super::program::Program;
use super::structure::{Lending, Nesting, Structure};
use super::violation::{Report, Violation};
use crate::ir::traits::Threads;

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
        if let Nesting::Loop {
            body,
            leading_arguments,
            leading_yields,
            ..
        } = definition.nesting()
        {
            let carried = program.arguments(body).skip(leading_arguments);
            let yielded = program.yields(body).into_iter().skip(leading_yields);
            for (argument, result) in carried.zip(yielded) {
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
/// A result of an `if` or a `conditional` continues a value if both arms yield
/// that value at the same position. A result of a loop continues the initial
/// value at its position.
pub(super) fn previous(program: Program<'_>, value: SSAValue) -> Option<SSAValue> {
    let (statement, index) = program.producer(value)?;
    let definition = program.definition(statement);
    match definition.nesting() {
        Nesting::Arms {
            arms: [then, other],
            inputs,
        } => {
            let then = entering(program, then, inputs, index)?;
            let other = entering(program, other, inputs, index)?;
            (then == other).then_some(then)
        }
        Nesting::Graph { body, inputs } => {
            let mut value = *program.graph_yields(body).get(index)?;
            loop {
                if let Some((graph, port)) = program.port(value) {
                    let inside = graph == body;
                    return if inside {
                        inputs.get(port).copied()
                    } else {
                        None
                    };
                }
                value = previous(program, value)?;
            }
        }
        Nesting::Loop { initial, .. } => initial.get(index).copied(),
        Nesting::Flat => {
            let threads = definition.threads();
            let pair = threads.iter().find(|(_, result)| value == (*result).into());
            pair.map(|(operand, _)| *operand)
        }
    }
}

/// Return the outer value that the arm `block` yields at position `index`.
///
/// Argument `k` of the arm continues `inputs[k]`.
fn entering(
    program: Program<'_>,
    block: Block,
    inputs: &[SSAValue],
    index: usize,
) -> Option<SSAValue> {
    let mut value = *program.yields(block).get(index)?;
    while program.home(value) == Some(block) {
        if let Some(position) = program
            .arguments(block)
            .position(|argument| argument == value)
        {
            return inputs.get(position).copied();
        }
        value = previous(program, value)?;
    }
    Some(value)
}
