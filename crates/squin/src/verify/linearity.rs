//! Check that the program consumes each wire, register and slot exactly once.

use kirin::prelude::*;
use kirin_scf::StructuredControlFlow;

use super::program::Program;
use super::violation::{Report, Rule};
use crate::language::Squin;
use crate::state::State;
use crate::types::SquinType;

/// Check `block` and every block below it.
pub(super) fn check(program: Program<'_>, block: Block, report: &mut Report) {
    Linearity { program, report }.block(block);
}

/// Count how often a block consumes each linear value.
///
/// The counts keep the order of the first use, so reports have a stable order.
#[derive(Default)]
struct Consumed(Vec<(SSAValue, usize)>);

impl Consumed {
    fn add(&mut self, value: SSAValue, uses: usize) {
        match self.0.iter_mut().find(|(seen, _)| *seen == value) {
            Some((_, count)) => *count += uses,
            None => self.0.push((value, uses)),
        }
    }

    fn count(&self, value: SSAValue) -> usize {
        let entry = self.0.iter().find(|(seen, _)| *seen == value);
        entry.map_or(0, |(_, count)| *count)
    }

    /// Remove `value` and return how often the block consumes it.
    fn take(&mut self, value: SSAValue) -> usize {
        let count = self.count(value);
        self.0.retain(|(seen, _)| *seen != value);
        count
    }

    fn values(&self) -> impl Iterator<Item = SSAValue> + '_ {
        self.0.iter().map(|(value, _)| *value)
    }
}

struct Linearity<'a, 'r> {
    program: Program<'a>,
    report: &'r mut Report,
}

impl Linearity<'_, '_> {
    /// Check `block` and return the linear values of outer blocks that it consumes.
    fn block(&mut self, block: Block) -> Consumed {
        let mut consumed = Consumed::default();
        for statement in self.program.body(block) {
            for operand in self.program.operands(statement) {
                if self.program.ty(operand).is_linear() {
                    consumed.add(operand, 1);
                }
            }
            for (value, uses) in self.nested(statement).0 {
                consumed.add(value, uses);
            }
        }
        for value in self.program.definitions(block) {
            self.settle(value, consumed.take(value), block);
        }
        consumed
    }

    /// Return the outer linear values that the nested blocks of `statement` consume.
    ///
    /// An `if` runs one arm, so it consumes a value once if each arm consumes it
    /// once. A loop body can run any number of times, so it must receive each
    /// linear value as a block argument.
    fn nested(&mut self, statement: Statement) -> Consumed {
        match self.program.structured(statement) {
            Some(StructuredControlFlow::If(branch)) => {
                let then = self.block(branch.then_block());
                let other = self.block(branch.else_block());
                let mut either = Consumed::default();
                for value in then.values().chain(other.values()) {
                    let (left, right) = (then.count(value), other.count(value));
                    if either.count(value) == 0 {
                        either.add(value, left.max(right));
                        if left != right {
                            self.fail(
                                Rule::Capture,
                                value,
                                "has a different number of uses in each arm of an `if`",
                            );
                        }
                    }
                }
                either
            }
            Some(StructuredControlFlow::For(repeat)) => {
                let captured = self.block(repeat.body());
                for value in captured.values() {
                    self.fail(
                        Rule::Capture,
                        value,
                        "enters a loop body from outside the loop",
                    );
                }
                captured
            }
            _ => Consumed::default(),
        }
    }

    /// Check the linear value `value` of `block`, which the block consumes `uses` times.
    fn settle(&mut self, value: SSAValue, uses: usize, block: Block) {
        let ty = self.program.ty(value);
        if ty.is_linear() && uses != 1 {
            self.fail(
                Rule::SingleUse,
                value,
                &format!("has the linear type {ty} and {uses} uses"),
            );
        }
        if ty == SquinType::Slot && !self.stays(value, block) {
            self.fail(
                Rule::SlotScope,
                value,
                "is a slot that leaves the block of its `borrow`",
            );
        }
    }

    /// Check that each statement that reads `slot` is a `release` of `block`.
    fn stays(&self, slot: SSAValue, block: Block) -> bool {
        let borrowed = self.program.producer(slot).is_some();
        borrowed
            && self.program.uses(slot).iter().all(|site| match *site {
                Use::StatementOperand { stmt, .. } => {
                    let releases = matches!(
                        self.program.definition(stmt),
                        Squin::State(State::Release { slot: filled, .. }) if *filled == slot
                    );
                    releases && self.program.parent(stmt) == Some(block)
                }
                Use::DiGraphYield { .. } => false,
            })
    }

    fn fail(&mut self, rule: Rule, value: SSAValue, problem: &str) {
        let name = self.program.name(value);
        self.report.add(rule, format!("{name} {problem}."));
    }
}
