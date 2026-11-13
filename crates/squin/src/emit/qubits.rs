//! Give each qubit a fixed index, as Stim and ppvm number their qubits.

use std::collections::HashMap;

use kirin::prelude::*;

use crate::analysis::address::{Address, Addresses, QubitId};
use crate::ir::{Squin, query};

/// Name a wire or register whose qubits the address analysis does not know.
#[derive(Debug)]
pub(super) struct UnknownQubit(pub(super) String);

/// Hold the index of each live qubit and the indices that freed qubits left.
///
/// An allocation takes a freed index before it takes a new one, so the indices
/// stay dense. The caller resets a reused index, because its qubit can hold
/// any state.
pub(super) struct Qubits<'a> {
    program: &'a StageInfo<Squin>,
    addresses: &'a Addresses<'a>,
    indices: HashMap<QubitId, u32>,
    freed: Vec<u32>,
    next: u32,
}

impl<'a> Qubits<'a> {
    pub(super) fn new(program: &'a StageInfo<Squin>, addresses: &'a Addresses<'a>) -> Self {
        Self {
            program,
            addresses,
            indices: HashMap::new(),
            freed: Vec::new(),
            next: 0,
        }
    }

    /// Return the number of indices that the program uses.
    pub(super) fn count(&self) -> u32 {
        self.next
    }

    /// Give an index to each qubit of the new wire or register `value`.
    ///
    /// The result holds each index with a flag that is true if a freed qubit
    /// had the index before.
    pub(super) fn allocate(&mut self, value: SSAValue) -> Result<Vec<(u32, bool)>, UnknownQubit> {
        let mut given = Vec::new();
        for qubit in self.qubits(value)? {
            let (index, reused) = match self.freed.pop() {
                Some(index) => (index, true),
                None => {
                    self.next += 1;
                    (self.next - 1, false)
                }
            };
            self.indices.insert(qubit, index);
            given.push((index, reused));
        }
        Ok(given)
    }

    /// Return the index of each qubit of the wire or register `value` to the free list.
    pub(super) fn release(&mut self, value: SSAValue) -> Result<(), UnknownQubit> {
        let indices = self.indices_of(value)?;
        self.freed.extend(indices);
        Ok(())
    }

    /// Return the index of each qubit of the wire or register `value`.
    pub(super) fn indices_of(&self, value: SSAValue) -> Result<Vec<u32>, UnknownQubit> {
        let qubits = self.qubits(value)?;
        let unknown = || UnknownQubit(query::name(self.program, value));
        qubits
            .iter()
            .map(|qubit| self.indices.get(qubit).copied().ok_or_else(unknown))
            .collect()
    }

    /// Return the index of the qubit of the wire `wire`.
    pub(super) fn index(&self, wire: SSAValue) -> Result<u32, UnknownQubit> {
        let indices = self.indices_of(wire)?;
        let unknown = || UnknownQubit(query::name(self.program, wire));
        indices.first().copied().ok_or_else(unknown)
    }

    /// Return the qubits of the wire or register `value`.
    fn qubits(&self, value: SSAValue) -> Result<Vec<QubitId>, UnknownQubit> {
        match self.addresses.of(value) {
            Address::Wire(qubit) => Ok(vec![qubit]),
            Address::Register(qubits) => Ok(qubits),
            _ => Err(UnknownQubit(query::name(self.program, value))),
        }
    }
}
