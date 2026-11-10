//! Follow one qubit or one register from statement to statement.

use kirin::prelude::{ResultValue, SSAValue};

use crate::gate::Gate;
use crate::language::Squin;
use crate::state::State;

/// Tell which result of a statement continues which linear operand.
///
/// A pair `(operand, result)` states that both values name the same qubit or
/// the same register. For example, `h %a -> Wire` pairs `%a` with its result.
pub trait Threads {
    /// Return each linear operand with the result that continues it.
    fn threads(&self) -> Vec<(SSAValue, ResultValue)>;
}

impl Threads for State {
    fn threads(&self) -> Vec<(SSAValue, ResultValue)> {
        match *self {
            State::Borrow {
                register,
                register_out,
                ..
            }
            | State::Release {
                register,
                register_out,
                ..
            }
            | State::Replace {
                register,
                register_out,
                ..
            }
            | State::Length {
                register,
                register_out,
                ..
            }
            | State::MeasureRegister {
                register,
                register_out,
                ..
            } => vec![(register, register_out)],
            State::Measure { wire, wire_out, .. } | State::Reset { wire, wire_out } => {
                vec![(wire, wire_out)]
            }
            State::Alloc { .. }
            | State::Free { .. }
            | State::AllocRegister { .. }
            | State::FreeRegister { .. }
            | State::Pack { .. }
            | State::Split { .. }
            | State::Join { .. } => Vec::new(),
        }
    }
}

impl Threads for Gate {
    fn threads(&self) -> Vec<(SSAValue, ResultValue)> {
        match *self {
            Gate::Fixed { wire, wire_out, .. }
            | Gate::Rotation { wire, wire_out, .. }
            | Gate::U3 { wire, wire_out, .. } => vec![(wire, wire_out)],
            Gate::Controlled {
                control,
                target,
                control_out,
                target_out,
                ..
            } => vec![(control, control_out), (target, target_out)],
        }
    }
}

impl Threads for Squin {
    fn threads(&self) -> Vec<(SSAValue, ResultValue)> {
        match self {
            Squin::State(state) => state.threads(),
            Squin::Gate(gate) => gate.threads(),
            _ => Vec::new(),
        }
    }
}
