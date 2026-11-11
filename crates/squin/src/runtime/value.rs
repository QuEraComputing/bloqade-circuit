use std::fmt;

use kirin::prelude::Typeof;
use kirin_arith::ArithValue;

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
    Number(ArithValue),
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
            Scalar::Number(value) => Value::Number(value),
            Scalar::Bool(value) => Value::Bool(value),
        }
    }
}

impl<M> Value<M> {
    pub(super) fn matches_type(&self, expected: SquinType) -> bool {
        match (self, expected) {
            (Self::Wire(_) | Self::Slot(_) | Self::Register(_), SquinType::Any) => false,
            (_, SquinType::Any) => true,
            (Self::Number(value), SquinType::Number(ty)) => value.type_of() == ty,
            (Self::Bool(_), SquinType::Bool)
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

    pub(super) fn type_name(&self) -> String {
        match self {
            Self::Number(value) => value.type_of().to_string(),
            Self::Register(qubits) => {
                let lent = qubits.iter().filter(|qubit| qubit.is_none()).count();
                format!("Register[{}; lent={lent}]", qubits.len())
            }
            Self::Bits(bits) => format!("Bits[{}]", bits.len()),
            _ => self.kind().to_string(),
        }
    }

    /// Return each qubit that this value owns.
    pub(super) fn qubits(&self) -> impl Iterator<Item = Qubit> + '_ {
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
            Value::Number(_) => "a number",
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

impl<M> From<ArithValue> for Value<M> {
    fn from(value: ArithValue) -> Self {
        Self::Number(value)
    }
}

macro_rules! from_scalar {
    ($($ty:ty),+ $(,)?) => {$(
        impl<M> From<$ty> for Value<M> {
            fn from(value: $ty) -> Self {
                Scalar::from(value).into()
            }
        }
    )+};
}

from_scalar!(
    i8, i16, i32, i64, i128, u8, u16, u32, u64, u128, f32, f64, bool
);
