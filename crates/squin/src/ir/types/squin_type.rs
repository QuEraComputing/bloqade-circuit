use kirin_arith::ArithType;
use std::fmt;

use kirin::prelude::{HasBottom, HasTop, Lattice, Placeholder, TypeLattice};

use super::Length;

/// Name the type of each value of a squin program.
///
/// `Wire`, `Slot` and `Register` are the linear types. A program must use each
/// value of a linear type exactly once.
#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq)]
pub enum SquinType {
    /// The type of a value that the compiler knows nothing about.
    Any,
    /// The type of a value that no execution produces.
    Bottom,
    /// A numeric type from Kirin's arithmetic dialect.
    Number(ArithType),
    /// A truth value, such as the condition of an `if`.
    Bool,
    /// The result of one measurement.
    MeasurementResult,
    /// An immutable array of measurement results.
    MeasurementResults(Length),
    /// One qubit at one point in the program.
    Wire,
    /// A token for one empty element of a register.
    ///
    /// `borrow` makes the token, and `release` consumes it to fill the element.
    Slot,
    /// An array of qubits, of which `lent` elements are empty.
    ///
    /// `Register[3]` holds 3 qubits. `Register[3; lent=1]` has lent 1 of them
    /// to a wire.
    Register { len: Length, lent: u32 },
}

impl SquinType {
    /// Return the type of a register of `len` qubits with every element in place.
    pub fn register(len: Length) -> Self {
        SquinType::Register { len, lent: 0 }
    }

    /// Check whether the type belongs to Kirin's arithmetic dialect.
    pub fn is_number(self) -> bool {
        matches!(self, SquinType::Number(_))
    }

    /// Check whether a program must use a value of this type exactly once.
    pub fn is_linear(self) -> bool {
        matches!(
            self,
            SquinType::Wire | SquinType::Slot | SquinType::Register { .. }
        )
    }
}

impl Lattice for SquinType {
    fn is_subseteq(&self, other: &Self) -> bool {
        use SquinType::{Any, Bottom, MeasurementResults, Register};
        match (*self, *other) {
            (Bottom, _) | (_, Any) => true,
            (MeasurementResults(left), MeasurementResults(right)) => left.is_subseteq(right),
            (
                Register { len, lent },
                Register {
                    len: other_len,
                    lent: other_lent,
                },
            ) => lent == other_lent && len.is_subseteq(other_len),
            (left, right) => left == right,
        }
    }

    fn join(&self, other: &Self) -> Self {
        use SquinType::{Any, Bottom, MeasurementResults, Register};
        match (*self, *other) {
            (Bottom, ty) | (ty, Bottom) => ty,
            (MeasurementResults(left), MeasurementResults(right)) => {
                MeasurementResults(left.join(right))
            }
            (
                Register { len, lent },
                Register {
                    len: other_len,
                    lent: other_lent,
                },
            ) if lent == other_lent => Register {
                len: len.join(other_len),
                lent,
            },
            (left, right) if left == right => left,
            _ => Any,
        }
    }

    fn meet(&self, other: &Self) -> Self {
        use SquinType::{Any, Bottom, MeasurementResults, Register};
        match (*self, *other) {
            (Any, ty) | (ty, Any) => ty,
            (MeasurementResults(left), MeasurementResults(right)) => {
                left.meet(right).map_or(Bottom, MeasurementResults)
            }
            (
                Register { len, lent },
                Register {
                    len: other_len,
                    lent: other_lent,
                },
            ) if lent == other_lent => len
                .meet(other_len)
                .map_or(Bottom, |len| Register { len, lent }),
            (left, right) if left == right => left,
            _ => Bottom,
        }
    }
}

impl HasBottom for SquinType {
    fn bottom() -> Self {
        SquinType::Bottom
    }
}

impl HasTop for SquinType {
    fn top() -> Self {
        SquinType::Any
    }
}

impl TypeLattice for SquinType {}

impl Placeholder for SquinType {
    fn placeholder() -> Self {
        SquinType::Any
    }
}

impl fmt::Display for SquinType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SquinType::Any => write!(f, "Any"),
            SquinType::Bottom => write!(f, "Bottom"),
            SquinType::Number(ty) => write!(f, "{ty}"),
            SquinType::Bool => write!(f, "Bool"),
            SquinType::MeasurementResult => write!(f, "MeasurementResult"),
            SquinType::MeasurementResults(len) => write!(f, "MeasurementResults[{len}]"),
            SquinType::Wire => write!(f, "Wire"),
            SquinType::Slot => write!(f, "Slot"),
            SquinType::Register { len, lent: 0 } => write!(f, "Register[{len}]"),
            SquinType::Register { len, lent } => write!(f, "Register[{len}; lent={lent}]"),
        }
    }
}

impl From<ArithType> for SquinType {
    fn from(ty: ArithType) -> Self {
        Self::Number(ty)
    }
}
