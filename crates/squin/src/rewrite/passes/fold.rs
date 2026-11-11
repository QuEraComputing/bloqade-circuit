//! Merge the phase rotations of a block that act on the same parity of qubits.
//!
//! The pass follows the idea of phase folding by Amy, Maslov and Mosca. It
//! gives each qubit that enters a run of gates a fresh path variable. An `x`
//! adds the constant 1 to the value of its qubit, and a `cx` adds the value of
//! the control to the target. So the value of each qubit stays a parity: a sum
//! modulo 2 of path variables, maybe with the constant 1 added. Every other
//! gate that changes the value gives its output a fresh variable.
//!
//! A phase gate such as `t` or `rz` multiplies the state by a phase that
//! depends on that parity only. Two phase gates on the same parity therefore
//! merge into one, wherever the parity occurs. The pass puts the merged
//! rotation at the last gate of the group, because every angle value exists
//! there.
//!
//! The pass drops global phases. A statement that consumes a wire, such as
//! `measure` or `release`, or that owns a block, ends every group.

use std::collections::HashMap;

use kirin::prelude::*;
use kirin_arith::Arith;

use crate::dialects::Squin;
use crate::dialects::gate::{Gate, Rz, S, SDag, T, TDag, Z};
use crate::ir::traits::Threads;
use crate::ir::types::SquinType;
use crate::rewrite::rules::{RuleError, functions};

/// Merge the phase rotations of every block and return the number of gates
/// that the pass removed.
pub fn fold_phases(rewriter: &mut Rewriter<'_, Squin>) -> Result<usize, RuleError> {
    let mut removed = 0;
    for block in blocks(rewriter.stage()) {
        for group in Scan::default().groups(rewriter.stage(), block) {
            removed += merge(rewriter, group)?;
        }
    }
    Ok(removed)
}

/// Hold a sum modulo 2 of path variables, maybe with the constant 1 added.
///
/// `variables` is sorted, so two equal sums have equal fields.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
struct Parity {
    variables: Vec<u32>,
    negated: bool,
}

impl Parity {
    fn fresh(variable: u32) -> Self {
        let variables = vec![variable];
        Parity {
            variables,
            negated: false,
        }
    }

    /// Return the parity with the constant 1 added.
    fn flipped(&self) -> Self {
        let variables = self.variables.clone();
        Parity {
            variables,
            negated: !self.negated,
        }
    }

    /// Return the sum modulo 2 of the two parities.
    fn plus(&self, other: &Self) -> Self {
        let (mut left, mut right) = (
            self.variables.iter().peekable(),
            other.variables.iter().peekable(),
        );
        let mut variables = Vec::new();
        loop {
            match (left.peek(), right.peek()) {
                (Some(a), Some(b)) if a == b => {
                    left.next();
                    right.next();
                }
                (Some(a), Some(b)) if a < b => variables.extend(left.next()),
                (Some(_), Some(_)) | (None, Some(_)) => variables.extend(right.next()),
                (Some(_), None) => variables.extend(left.next()),
                (None, None) => break,
            }
        }
        let negated = self.negated != other.negated;
        Parity { variables, negated }
    }
}

/// Name the phase of one phase gate.
#[derive(Clone, Copy, Debug)]
enum Phase {
    /// A multiple of an eighth of a turn, such as 1 for `t` and 2 for `s`.
    Eighths(i64),
    /// The angle of an `rz`, in turns.
    Angle(SSAValue),
}

/// Return the phase of `gate` if it is a phase gate.
fn phase(gate: &Gate) -> Option<Phase> {
    Some(match gate {
        Gate::Z(_) => Phase::Eighths(4),
        Gate::S(_) => Phase::Eighths(2),
        Gate::SDag(_) => Phase::Eighths(-2),
        Gate::T(_) => Phase::Eighths(1),
        Gate::TDag(_) => Phase::Eighths(-1),
        Gate::Rz(Rz { angle, .. }) => Phase::Angle(*angle),
        _ => return None,
    })
}

/// Hold one phase gate of a group.
///
/// `negated` is true if the qubit of the gate holds the parity of the group
/// with the constant 1 added. A rotation by `a` on that qubit is a rotation by
/// `-a` on the parity of the group, up to a global phase.
struct Occurrence {
    statement: Statement,
    phase: Phase,
    negated: bool,
}

/// Hold the phase gates that act on one parity.
///
/// If `constant` is true, the parity has no variable. The qubit then has the
/// same value on every path, and each of the gates is a global phase.
struct Group {
    occurrences: Vec<Occurrence>,
    constant: bool,
}

/// Collect the groups of one block.
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
    fn groups(mut self, stage: &StageInfo<Squin>, block: Block) -> Vec<Group> {
        for statement in block.statements(stage) {
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

/// Return the input wire and the output wire of the one-qubit gate `statement`.
fn wires(stage: &StageInfo<Squin>, statement: Statement) -> (SSAValue, ResultValue) {
    match statement.definition(stage) {
        Squin::Gate(gate) => gate.threads()[0],
        _ => unreachable!("a group holds phase gates only"),
    }
}

/// Name a fixed phase gate that the pass can emit.
#[derive(Clone, Copy)]
enum Fixed {
    Z,
    S,
    SDag,
    T,
    TDag,
}

/// Return the fewest fixed gates whose phase is `eighths` eighths of a turn.
fn fixed(eighths: i64) -> &'static [Fixed] {
    match eighths.rem_euclid(8) {
        1 => &[Fixed::T],
        2 => &[Fixed::S],
        3 => &[Fixed::S, Fixed::T],
        4 => &[Fixed::Z],
        5 => &[Fixed::Z, Fixed::T],
        6 => &[Fixed::SDag],
        7 => &[Fixed::TDag],
        _ => &[],
    }
}

/// Replace the gates of `group` by the merged rotation and return the number
/// of gates that the replacement removed.
///
/// The group stays as it is if the replacement has as many gates.
fn merge(rewriter: &mut Rewriter<'_, Squin>, group: Group) -> Result<usize, RuleError> {
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
    for gate in gates {
        wire = place(rewriter, anchor.0, wire, |wire, wire_out| match gate {
            Fixed::Z => Gate::Z(Z { wire, wire_out }),
            Fixed::S => Gate::S(S { wire, wire_out }),
            Fixed::SDag => Gate::SDag(SDag { wire, wire_out }),
            Fixed::T => Gate::T(T { wire, wire_out }),
            Fixed::TDag => Gate::TDag(TDag { wire, wire_out }),
        })?;
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
) -> Result<SSAValue, RuleError> {
    let output = rewriter.new_result(SquinType::Wire);
    rewriter.insert_before(anchor, Squin::Gate(make(wire, output)))?;
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
) -> Result<Option<SSAValue>, RuleError> {
    let mut sum: Option<SSAValue> = None;
    for &(angle, negative) in angles {
        let term = if negative {
            let result = rewriter.new_result(SquinType::Float);
            let negated = Arith::Neg {
                operand: angle,
                result,
            };
            rewriter.insert_before(anchor, Squin::Arith(negated))?;
            result.into()
        } else {
            angle
        };
        sum = Some(match sum {
            None => term,
            Some(lhs) => {
                let result = rewriter.new_result(SquinType::Float);
                let added = Arith::Add {
                    lhs,
                    rhs: term,
                    result,
                };
                rewriter.insert_before(anchor, Squin::Arith(added))?;
                result.into()
            }
        });
    }
    Ok(sum)
}

/// Return every block of every function, each parent before its children.
fn blocks(stage: &StageInfo<Squin>) -> Vec<Block> {
    let definitions = functions(stage);
    let bodies = definitions.iter().flat_map(|function| function.cfgs(stage));
    let mut blocks: Vec<Block> = bodies.flat_map(|body| body.blocks(stage)).collect();
    let mut next = 0;
    while let Some(&block) = blocks.get(next) {
        for statement in block.statements(stage) {
            blocks.extend(statement.blocks(stage).copied());
        }
        next += 1;
    }
    blocks
}
