use std::fmt;

use super::Failure;
use crate::ir::types::{Length, Scalar, SquinType};

/// Name one qubit of a backend.
#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq)]
pub struct Qubit(pub u32);

impl fmt::Display for Qubit {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

/// Hold the run-time value of one SSA value.
///
/// `M` is the type that the backend gives for one measurement result.
#[derive(Clone, Debug, PartialEq)]
pub enum Value<M> {
    Int(i64),
    Float(f64),
    Bool(bool),
    Bit(M),
    Bits(Vec<M>),
    Wire(Qubit),
    /// The index of the register element that a `borrow` left empty.
    Slot(usize),
    /// The qubits of a register, with `None` at each empty element.
    Register(Vec<Option<Qubit>>),
}

impl<M> From<Scalar> for Value<M> {
    fn from(scalar: Scalar) -> Self {
        match scalar {
            Scalar::Int(value) => Value::Int(value),
            Scalar::Float(value) => Value::Float(value),
            Scalar::Bool(value) => Value::Bool(value),
        }
    }
}

impl<M> Value<M> {
    pub(crate) fn matches_type(&self, expected: SquinType) -> bool {
        match (self, expected) {
            (Self::Wire(_) | Self::Slot(_) | Self::Register(_), SquinType::Any) => false,
            (_, SquinType::Any) => true,
            (Self::Int(_), SquinType::Int)
            | (Self::Float(_), SquinType::Float)
            | (Self::Bool(_), SquinType::Bool)
            | (Self::Bit(_), SquinType::Bit)
            | (Self::Wire(_), SquinType::Wire)
            | (Self::Slot(_), SquinType::Slot) => true,
            (Self::Bits(bits), SquinType::Bits(len)) => {
                Length::Known(bits.len() as u64).is_subseteq(len)
            }
            (Self::Register(qubits), SquinType::Register { len, lent }) => {
                Length::Known(qubits.len() as u64).is_subseteq(len)
                    && qubits.iter().filter(|qubit| qubit.is_none()).count() == lent as usize
            }
            _ => false,
        }
    }

    pub(crate) fn type_name(&self) -> String {
        match self {
            Self::Register(qubits) => {
                let lent = qubits.iter().filter(|qubit| qubit.is_none()).count();
                format!("Register[{}; lent={lent}]", qubits.len())
            }
            Self::Bits(bits) => format!("Bits[{}]", bits.len()),
            _ => self.kind().to_string(),
        }
    }

    /// Return each qubit that this value owns.
    pub(crate) fn qubits(&self) -> impl Iterator<Item = Qubit> + '_ {
        let wire = match self {
            Self::Wire(qubit) => Some(*qubit),
            _ => None,
        };
        let register = match self {
            Self::Register(qubits) => qubits.as_slice(),
            _ => &[],
        };
        wire.into_iter().chain(register.iter().flatten().copied())
    }

    /// Return the name of the kind of the value for an error message.
    pub fn kind(&self) -> &'static str {
        match self {
            Value::Int(_) => "an integer",
            Value::Float(_) => "a float",
            Value::Bool(_) => "a truth value",
            Value::Bit(_) => "a measurement result",
            Value::Bits(_) => "an array of measurement results",
            Value::Wire(_) => "a wire",
            Value::Slot(_) => "a slot",
            Value::Register(_) => "a register",
        }
    }

    /// Return the failure of a statement that needs `expected` and read this value.
    pub fn is_not(&self, expected: &'static str) -> Failure {
        let found = self.kind();
        Failure::Kind { expected, found }
    }
}
