//! Describe phase gates and the groups that share one parity.

use kirin::prelude::*;

use crate::ir::dialects::gate::{Gate, Rz};

/// Name the phase of one phase gate.
#[derive(Clone, Copy, Debug)]
pub(super) enum Phase {
    /// A multiple of an eighth of a turn, such as 1 for `t` and 2 for `s`.
    Eighths(i64),
    /// The angle of an `rz`, in turns.
    Angle(SSAValue),
}

/// Return the phase of `gate` if it is a phase gate.
pub(super) fn phase(gate: &Gate) -> Option<Phase> {
    Some(match gate {
        Gate::Z(_) => Phase::Eighths(4),
        Gate::S(_) => Phase::Eighths(2),
        Gate::SDag(_) => Phase::Eighths(-2),
        Gate::T(_) => Phase::Eighths(1),
        Gate::TDag(_) => Phase::Eighths(-1),
        Gate::Rz(Rz { angle, .. }) => Phase::Angle(*angle),
        _ => return None,
    })
}

/// Hold one phase gate of a group.
///
/// `negated` is true if the qubit of the gate holds the parity of the group
/// with the constant 1 added. A rotation by `a` on that qubit is a rotation by
/// `-a` on the parity of the group, up to a global phase.
pub(super) struct Occurrence {
    pub(super) statement: Statement,
    pub(super) phase: Phase,
    pub(super) negated: bool,
}

/// Hold the phase gates that act on one parity.
///
/// If `constant` is true, the parity has no variable. The qubit then has the
/// same value on every path, and each of the gates is a global phase.
pub(super) struct Group {
    pub(super) occurrences: Vec<Occurrence>,
    pub(super) constant: bool,
}
