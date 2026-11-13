//! Write squin programs in the formats of other tools.
//!
//! An emitter reads the IR and the facts of an analysis. It walks each block in
//! program order and writes one instruction for each quantum statement. `stim`
//! writes Stim circuits, and `ppvm` writes programs for QuEra's ppvm.

pub mod ppvm;
mod qubits;
pub mod stim;
