//! Name the operations that the squin rules need from a value domain.

use kirin::prelude::Statement;

/// Give the squin forward rules the values of qubits and registers.
///
/// A gate needs no operation here, because its output wire carries the qubit
/// of its input wire. The verifier proves that a `release` returns the borrowed
/// qubit to its element, so a borrow and a release leave a register unchanged.
pub trait QuantumValue: Sized {
    /// Return the qubit at `offset` of the allocation `site`.
    ///
    /// An abstract engine can run a statement more than once. The site and the
    /// offset name the qubit, so each run gives the same value.
    fn qubit(site: Statement, offset: u32) -> Self;

    /// Return the register that the statement `site` allocates with `size` qubits.
    fn allocated_register(site: Statement, size: &Self) -> Self;

    /// Return the qubit at `index` of `register`.
    fn element(register: &Self, index: &Self) -> Self;

    /// Put `wire` at `index` of `register`, and return the new register and the old qubit.
    fn replaced(register: &Self, index: &Self, wire: Self) -> (Self, Self);

    /// Return the register that holds `wires` in order.
    fn packed(wires: Vec<Self>) -> Self;

    /// Return the elements of `register` before `index`, and the other elements.
    fn split_at(register: &Self, index: &Self) -> (Self, Self);

    /// Return the register of the elements of `first` and then of `second`.
    fn concatenated(first: &Self, second: &Self) -> Self;

    /// Return the number of qubits of `register`.
    fn length(register: &Self) -> Self;

    /// Return a value that the domain does not track, such as a measurement result.
    fn untracked() -> Self;
}
