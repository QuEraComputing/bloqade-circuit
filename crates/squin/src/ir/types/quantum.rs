//! Name the types that the quantum dialects fix for their results.

use kirin::prelude::CompileTimeValue;

use super::{Length, SquinType};

/// Give the types that the quantum dialects fix for their results.
///
/// The qubit, register, gate and bits dialects are generic over their type
/// lattice, as the Kirin dialects are. A language implements this trait for its
/// own lattice and then wraps the dialects with that lattice.
pub trait QuantumTypes: CompileTimeValue {
    /// Return the type of one qubit at one point in the program.
    fn wire() -> Self;
    /// Return the type of the token for one empty register element.
    fn slot() -> Self;
    /// Return the type of one measurement result.
    fn bit() -> Self;
    /// Return the type of an array of `length` measurement results.
    fn bits(length: Length) -> Self;
    /// Return the type of a register of `length` qubits with every element in place.
    fn register(length: Length) -> Self;
    /// Return the type of a register length or a register index.
    fn index() -> Self;
}

impl QuantumTypes for SquinType {
    fn wire() -> Self {
        SquinType::Wire
    }

    fn slot() -> Self {
        SquinType::Slot
    }

    fn bit() -> Self {
        SquinType::Bit
    }

    fn bits(length: Length) -> Self {
        SquinType::Bits(length)
    }

    fn register(length: Length) -> Self {
        SquinType::register(length)
    }

    fn index() -> Self {
        SquinType::Number(kirin_arith::ArithType::I64)
    }
}
