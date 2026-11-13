//! Lend a register element at an index that the program computes at run time.
//!
//! The emitter handles such a `borrow` with a register table: a vihaco heap
//! array that holds the qubit index of each element. A run-time `borrow` and
//! its `release` never change which qubit sits at which element, so the
//! table of a register is a constant. The emitter therefore builds each
//! distinct table once, in the prologue of `@main`, and a `borrow` in a loop
//! reads it on every run.

use kirin::prelude::*;

use super::PpvmEmitter;
use super::PpvmError;
use super::locals::{Kind, Slot};

impl PpvmEmitter<'_> {
    /// Lend element `index` of `register` to `wire`, with `index` known only at run time.
    ///
    /// The program reads the qubit index from the register table and stores
    /// it in a new `u64` slot, which gates on `wire` then load.
    pub(super) fn borrow_at_run_time(
        &mut self,
        register: SSAValue,
        index: SSAValue,
        wire: SSAValue,
    ) -> Result<(), PpvmError> {
        let qubits = self.qubits.indices_of(register)?;
        let (table, _) = self.table(qubits);
        let slot = self.fresh_slot(Kind::U64);
        self.line(format!("cpu::cpu.load heap_ref, {table}"));
        self.load(index)?;
        self.line("cpu::cpu.get_item".to_string());
        self.store_into(&[slot]);
        self.set(wire, vec![slot])
    }

    /// Return the slot of the table that holds `qubits`, and build the table in the prologue once.
    fn table(&mut self, qubits: Vec<u32>) -> Slot {
        if let Some(slot) = self.tables.get(&qubits) {
            return *slot;
        }
        let slot = self.fresh_slot(Kind::HeapRef);
        for qubit in &qubits {
            self.prologue.push(format!("cpu::cpu.const u64, {qubit}"));
        }
        self.prologue
            .push(format!("cpu::cpu.heap_alloc {}", qubits.len()));
        self.prologue
            .push(format!("cpu::cpu.store heap_ref, {}", slot.0));
        self.tables.insert(qubits, slot);
        slot
    }
}
