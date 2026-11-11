//! Check that the program consumes each wire, register and slot exactly once.

use std::collections::HashMap;

use kirin::prelude::*;

use super::program::Program;
use super::violation::{Report, Violation};
use crate::ir::traits::{Lending, Nesting, Structure};
use crate::ir::types::SquinType;

/// Check `block` and every block below it.
pub(super) fn check(program: Program<'_>, block: Block, report: &mut Report) {
    Linearity { program, report }.block(block);
}

/// Count how often a block consumes each linear value.
///
/// `order` keeps the values in the order of their first use, so reports have a
/// stable order.
#[derive(Default)]
struct Consumed {
    uses: HashMap<SSAValue, usize>,
    order: Vec<SSAValue>,
}

impl Consumed {
    fn add(&mut self, value: SSAValue, uses: usize) {
        let count = self.uses.entry(value).or_insert_with(|| {
            self.order.push(value);
            0
        });
        *count += uses;
    }

    fn count(&self, value: SSAValue) -> usize {
        self.uses.get(&value).copied().unwrap_or(0)
    }

    /// Remove `value` and return how often the block consumes it.
    fn take(&mut self, value: SSAValue) -> usize {
        self.uses.remove(&value).unwrap_or(0)
    }

    /// Return each value that the block still holds, with its count.
    fn entries(&self) -> impl Iterator<Item = (SSAValue, usize)> + '_ {
        self.order.iter().filter_map(|value| {
            let count = self.uses.get(value)?;
            Some((*value, *count))
        })
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
            for (value, uses) in self.nested(statement).entries() {
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
        match self.program.definition(statement).nesting() {
            Nesting::Flat => Consumed::default(),
            Nesting::Arms([then, other]) => {
                let (then, other) = (self.block(then), self.block(other));
                let mut either = Consumed::default();
                for (value, _) in then.entries().chain(other.entries()) {
                    let (left, right) = (then.count(value), other.count(value));
                    if either.count(value) == 0 {
                        either.add(value, left.max(right));
                        if left != right {
                            let value = self.program.named(value);
                            self.report.add(Violation::UnevenArms { value });
                        }
                    }
                }
                either
            }
            Nesting::Loop { body, .. } => {
                let captured = self.block(body);
                for (value, _) in captured.entries() {
                    let value = self.program.named(value);
                    self.report.add(Violation::LoopCapture { value });
                }
                captured
            }
        }
    }

    /// Check the value `value` of `block`, which the block consumes `uses` times.
    fn settle(&mut self, value: SSAValue, uses: usize, block: Block) {
        let ty = self.program.ty(value);
        if ty.is_linear() && uses != 1 {
            let value = self.program.named(value);
            self.report.add(Violation::Uses { value, ty, uses });
        }
        if ty == SquinType::Slot && !self.stays(value, block) {
            let slot = self.program.named(value);
            self.report.add(Violation::SlotEscapes { slot });
        }
    }

    /// Check that each statement that reads `slot` is a `release` of `block`.
    fn stays(&self, slot: SSAValue, block: Block) -> bool {
        let borrowed = self.program.producer(slot).is_some();
        borrowed
            && self.program.uses(slot).iter().all(|site| match *site {
                Use::StatementOperand { stmt, .. } => {
                    let releases = matches!(
                        self.program.definition(stmt).lending(),
                        Some(Lending::Release { slot: filled, .. }) if filled == slot
                    );
                    releases && self.program.parent(stmt) == Some(block)
                }
                Use::DiGraphYield { .. } => false,
            })
    }
}
