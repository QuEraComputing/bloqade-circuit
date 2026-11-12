//! Define the address lattice and its quantum operations.

use kirin::prelude::{HasBottom, HasTop, Lattice, Statement, Widen};

use crate::analysis::QuantumValue;

/// Name one qubit by the statement that allocates it and its position there.
///
/// `alloc` allocates the qubit at offset 0, and `alloc_register` allocates one
/// qubit at each offset.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct QubitId {
    pub site: Statement,
    pub offset: u32,
}

/// Hold what the analysis knows about one value.
///
/// The lattice is flat: two different facts join to `Top`.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Address {
    /// No execution reaches the value.
    Bottom,
    /// The value is this integer in every execution.
    Int(i64),
    /// The value is this truth value in every execution.
    Bool(bool),
    /// The wire carries this qubit.
    Wire(QubitId),
    /// The register holds these qubits in element order.
    Register(Vec<QubitId>),
    /// The analysis does not know the value.
    Top,
}

impl Address {
    /// Return the qubit of a wire fact.
    pub fn qubit(&self) -> Option<QubitId> {
        match self {
            Address::Wire(qubit) => Some(*qubit),
            _ => None,
        }
    }

    /// Return the qubits of a register fact.
    pub fn qubits(&self) -> Option<&[QubitId]> {
        match self {
            Address::Register(qubits) => Some(qubits),
            _ => None,
        }
    }

    /// Return the element of `register` at the integer `index`.
    fn position(register: &Self, index: &Self) -> Option<(Vec<QubitId>, usize)> {
        match (register, index) {
            (Address::Register(qubits), Address::Int(index)) => {
                let position = usize::try_from(*index).ok()?;
                (position < qubits.len()).then(|| (qubits.clone(), position))
            }
            _ => None,
        }
    }
}

impl Lattice for Address {
    fn join(&self, other: &Self) -> Self {
        match (self, other) {
            (Address::Bottom, fact) | (fact, Address::Bottom) => fact.clone(),
            (left, right) if left == right => left.clone(),
            _ => Address::Top,
        }
    }

    fn meet(&self, other: &Self) -> Self {
        match (self, other) {
            (Address::Top, fact) | (fact, Address::Top) => fact.clone(),
            (left, right) if left == right => left.clone(),
            _ => Address::Bottom,
        }
    }

    fn is_subseteq(&self, other: &Self) -> bool {
        self.join(other) == *other
    }
}

impl HasBottom for Address {
    fn bottom() -> Self {
        Address::Bottom
    }
}

impl HasTop for Address {
    fn top() -> Self {
        Address::Top
    }
}

/// Widen by joining, because the flat lattice has a finite height.
impl Widen for Address {
    fn widen(&self, other: &Self) -> Self {
        self.join(other)
    }
}

impl QuantumValue for Address {
    fn qubit(site: Statement, offset: u32) -> Self {
        Address::Wire(QubitId { site, offset })
    }

    fn allocated_register(site: Statement, size: &Self) -> Self {
        match size {
            Address::Int(size) => match u32::try_from(*size) {
                Ok(size) => {
                    Address::Register((0..size).map(|offset| QubitId { site, offset }).collect())
                }
                Err(_) => Address::Top,
            },
            Address::Bottom => Address::Bottom,
            _ => Address::Top,
        }
    }

    fn element(register: &Self, index: &Self) -> Self {
        match Address::position(register, index) {
            Some((qubits, position)) => Address::Wire(qubits[position]),
            None => Address::Top,
        }
    }

    fn replaced(register: &Self, index: &Self, wire: Self) -> (Self, Self) {
        match (Address::position(register, index), wire) {
            (Some((mut qubits, position)), Address::Wire(qubit)) => {
                let old = std::mem::replace(&mut qubits[position], qubit);
                (Address::Register(qubits), Address::Wire(old))
            }
            (Some((qubits, position)), _) => (Address::Top, Address::Wire(qubits[position])),
            (None, _) => (Address::Top, Address::Top),
        }
    }

    fn packed(wires: Vec<Self>) -> Self {
        let qubits = wires.iter().map(Address::qubit);
        qubits
            .collect::<Option<Vec<_>>>()
            .map_or(Address::Top, Address::Register)
    }

    fn split_at(register: &Self, index: &Self) -> (Self, Self) {
        match (register, index) {
            (Address::Register(qubits), Address::Int(index)) => {
                match usize::try_from(*index)
                    .ok()
                    .filter(|cut| *cut <= qubits.len())
                {
                    Some(cut) => {
                        let (before, after) = qubits.split_at(cut);
                        (
                            Address::Register(before.to_vec()),
                            Address::Register(after.to_vec()),
                        )
                    }
                    None => (Address::Top, Address::Top),
                }
            }
            _ => (Address::Top, Address::Top),
        }
    }

    fn concatenated(first: &Self, second: &Self) -> Self {
        match (first, second) {
            (Address::Register(first), Address::Register(second)) => {
                Address::Register(first.iter().chain(second).copied().collect())
            }
            _ => Address::Top,
        }
    }

    fn length(register: &Self) -> Self {
        match register {
            Address::Register(qubits) => Address::Int(qubits.len() as i64),
            _ => Address::Top,
        }
    }

    fn untracked() -> Self {
        Address::Top
    }
}
