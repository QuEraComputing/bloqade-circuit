//! Check that the program consumes each wire, register and slot exactly once.

use std::collections::HashMap;

use kirin::prelude::*;

use super::program::Program;
use super::structure::{Lending, Nesting, Structure};
use super::violation::{Report, Violation};
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

    /// Check that each linear value of `graph` has one use, and that no capture is linear.
    ///
    /// A node operand and a yield each consume a value once.
    fn graph(&mut self, graph: DiGraph) {
        for value in self.program.capture_ports(graph) {
            let ty = self.program.ty(value);
            if ty.is_linear() {
                let value = self.program.named(value);
                self.report.add(Violation::LinearCapture { value, ty });
            }
        }
        let mut consumed = Consumed::default();
        let reads = self
            .program
            .nodes(graph)
            .into_iter()
            .flat_map(|node| self.program.operands(node));
        for value in reads.chain(self.program.graph_yields(graph)) {
            if self.program.ty(value).is_linear() {
                consumed.add(value, 1);
            }
        }
        for value in self.program.graph_definitions(graph) {
            self.count(value, consumed.take(value));
            // A slot belongs to the block of its `borrow`, so no graph can hold one.
            if self.program.ty(value) == SquinType::Slot {
                let slot = self.program.named(value);
                self.report.add(Violation::SlotEscapes { slot });
            }
        }
    }

    /// Return the outer linear values that the nested blocks of `statement` consume.
    ///
    /// An arm and a loop body must receive each linear value as a block
    /// argument: an arm through the inputs of a `conditional`, and a loop body
    /// through its carried values.
    fn nested(&mut self, statement: Statement) -> Consumed {
        match self.program.definition(statement).nesting() {
            Nesting::Flat => Consumed::default(),
            // The scope check proves that a graph reads no outer value.
            Nesting::Graph { body, .. } => {
                self.graph(body);
                Consumed::default()
            }
            Nesting::Arms {
                arms: [then, other],
                ..
            } => {
                let (then, other) = (self.block(then), self.block(other));
                let mut either = Consumed::default();
                for (value, _) in then.entries().chain(other.entries()) {
                    if either.count(value) == 0 {
                        either.add(value, then.count(value).max(other.count(value)));
                        let value = self.program.named(value);
                        self.report.add(Violation::ArmCapture { value });
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
        self.count(value, uses);
        if self.program.ty(value) == SquinType::Slot && !self.stays(value, block) {
            let slot = self.program.named(value);
            self.report.add(Violation::SlotEscapes { slot });
        }
    }

    /// Check that a linear `value` has exactly one of its `uses`.
    fn count(&mut self, value: SSAValue, uses: usize) {
        let ty = self.program.ty(value);
        if ty.is_linear() && uses != 1 {
            let value = self.program.named(value);
            self.report.add(Violation::Uses { value, ty, uses });
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
