use super::{Failure, Qubit};

/// Name one gate with the values of its angles in turns.
///
/// Each variant has the name of its statement in the gate dialect.
#[derive(Clone, Copy, Debug, PartialEq)]
#[non_exhaustive]
pub enum Operation {
    X,
    Y,
    Z,
    H,
    S,
    SDag,
    T,
    TDag,
    SqrtX,
    SqrtXDag,
    SqrtY,
    SqrtYDag,
    Rx(f64),
    Ry(f64),
    Rz(f64),
    U3(f64, f64, f64),
    CX,
    CY,
    CZ,
}

/// Carry out the quantum operations of a kernel.
///
/// The evaluator computes every classical value and every register index. It
/// calls the backend with the qubits that each operation acts on. A backend can
/// simulate the operations or write them in the format of a target.
pub trait Backend {
    /// The value that the backend gives for one measurement.
    type Bit: Clone;

    /// Return a qubit in the zero state.
    fn alloc(&mut self) -> Result<Qubit, Failure>;

    /// End the life of `qubit`. A later `alloc` can return it again.
    fn free(&mut self, qubit: Qubit) -> Result<(), Failure>;

    /// Apply `operation` to `qubits`, which hold the control before the target.
    fn gate(&mut self, operation: Operation, qubits: &[Qubit]) -> Result<(), Failure>;

    /// Measure `qubits` and return one result for each qubit, in order.
    fn measure(&mut self, qubits: &[Qubit]) -> Result<Vec<Self::Bit>, Failure>;

    /// Return `qubit` to the zero state.
    fn reset(&mut self, qubit: Qubit) -> Result<(), Failure>;
}
