//! Collect phase gates that act on the same parity within a graph.

use std::collections::HashMap;

use kirin::prelude::*;

use super::group::{Group, Occurrence, Phase, phase};
use super::parity::Parity;
use crate::ir::Squin;
use crate::ir::dialects::gate::Gate;
use crate::ir::traits::Threads;
use crate::ir::types::SquinType;

/// Collect the groups of `statements`, which come in dependency order.
pub(super) fn groups(stage: &StageInfo<Squin>, statements: &[Statement]) -> Vec<Group> {
    Scan::default().groups(stage, statements)
}

/// Collect the groups of one graph.
#[derive(Default)]
struct Scan {
    parities: HashMap<SSAValue, Parity>,
    open: HashMap<Vec<u32>, Vec<Occurrence>>,
    /// The keys of `open` in the order of their first gate, for a stable order.
    order: Vec<Vec<u32>>,
    done: Vec<Group>,
    next: u32,
}

impl Scan {
    fn groups(mut self, stage: &StageInfo<Squin>, statements: &[Statement]) -> Vec<Group> {
        for &statement in statements {
            match statement.definition(stage) {
                Squin::Gate(gate) => self.gate(statement, gate),
                _ if ends_groups(stage, statement) => self.close(),
                _ => {}
            }
        }
        self.close();
        self.done
    }

    fn gate(&mut self, statement: Statement, gate: &Gate) {
        let threads = gate.threads();
        let inputs: Vec<Parity> = threads.iter().map(|(wire, _)| self.parity(*wire)).collect();
        let outputs = if let Some(phase) = phase(gate) {
            self.record(statement, phase, &inputs[0]);
            inputs
        } else {
            match gate {
                Gate::X(_) => vec![inputs[0].flipped()],
                Gate::CX(_) => vec![inputs[0].clone(), inputs[1].plus(&inputs[0])],
                // A `cz` is diagonal, so it keeps the value of each qubit.
                Gate::CZ(_) => inputs,
                _ => threads.iter().map(|_| self.fresh()).collect(),
            }
        };
        for ((_, output), parity) in threads.iter().zip(outputs) {
            self.parities.insert((*output).into(), parity);
        }
    }

    fn record(&mut self, statement: Statement, phase: Phase, parity: &Parity) {
        let occurrence = Occurrence {
            statement,
            phase,
            negated: parity.negated,
        };
        let key = parity.variables.clone();
        let group = self.open.entry(key.clone()).or_default();
        if group.is_empty() {
            self.order.push(key);
        }
        group.push(occurrence);
    }

    /// Return the parity of `wire`, and give it a fresh variable if it has none.
    fn parity(&mut self, wire: SSAValue) -> Parity {
        if let Some(parity) = self.parities.get(&wire) {
            return parity.clone();
        }
        let parity = self.fresh();
        self.parities.insert(wire, parity.clone());
        parity
    }

    fn fresh(&mut self) -> Parity {
        self.next += 1;
        Parity::fresh(self.next)
    }

    /// End every open group.
    fn close(&mut self) {
        for key in self.order.drain(..) {
            let occurrences = self.open.remove(&key).unwrap_or_default();
            let constant = key.is_empty();
            self.done.push(Group {
                occurrences,
                constant,
            });
        }
    }
}

/// Check whether `statement` consumes a wire or owns a block.
fn ends_groups(stage: &StageInfo<Squin>, statement: Statement) -> bool {
    let mut operands = statement.arguments(stage);
    let consumes = operands.any(|value| *value.expect_info(stage).ty() == SquinType::Wire);
    consumes || statement.blocks(stage).next().is_some()
}
