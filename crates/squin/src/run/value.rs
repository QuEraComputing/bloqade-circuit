use std::fmt;

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

impl<M> Value<M> {
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
}
