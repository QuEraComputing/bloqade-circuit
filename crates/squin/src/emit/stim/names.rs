//! Name the Stim instruction of each squin gate.

use super::StimError;
use crate::ir::dialects::gate::Gate;

/// Return the Stim name of a Clifford gate.
///
/// Stim holds Clifford gates only, so `t`, the rotations and `u3` have no name.
pub(super) fn gate_name(gate: &Gate) -> Option<&'static str> {
    Some(match gate {
        Gate::X(_) => "X",
        Gate::Y(_) => "Y",
        Gate::Z(_) => "Z",
        Gate::H(_) => "H",
        Gate::S(_) => "S",
        Gate::SDag(_) => "S_DAG",
        Gate::SqrtX(_) => "SQRT_X",
        Gate::SqrtXDag(_) => "SQRT_X_DAG",
        Gate::SqrtY(_) => "SQRT_Y",
        Gate::SqrtYDag(_) => "SQRT_Y_DAG",
        Gate::CX(_) => "CX",
        Gate::CY(_) => "CY",
        Gate::CZ(_) => "CZ",
        _ => return None,
    })
}

pub(super) fn unsupported(gate: &Gate) -> StimError {
    let name = format!("{gate:?}");
    let name = name.split('(').next().unwrap_or("this gate").to_string();
    StimError::Unsupported(format!("the gate {name}"))
}
