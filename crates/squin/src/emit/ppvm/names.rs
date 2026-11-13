//! Name the ppvm circuit instruction of each squin gate.

use kirin::prelude::SSAValue;

use crate::ir::dialects::gate::Gate;

/// Return the ppvm name of `gate`, or `None` for `cy`, which ppvm lacks.
pub(super) fn gate_name(gate: &Gate) -> Option<&'static str> {
    Some(match gate {
        Gate::X(_) => "x",
        Gate::Y(_) => "y",
        Gate::Z(_) => "z",
        Gate::H(_) => "h",
        Gate::S(_) => "s",
        Gate::SDag(_) => "s_adj",
        Gate::T(_) => "t",
        Gate::TDag(_) => "t_adj",
        Gate::SqrtX(_) => "sqrt_x",
        Gate::SqrtXDag(_) => "sqrt_x_adj",
        Gate::SqrtY(_) => "sqrt_y",
        Gate::SqrtYDag(_) => "sqrt_y_adj",
        Gate::Rx(_) => "rx",
        Gate::Ry(_) => "ry",
        Gate::Rz(_) => "rz",
        Gate::U3(_) => "u3",
        Gate::CX(_) => "cnot",
        Gate::CZ(_) => "cz",
        Gate::CY(_) => return None,
    })
}

/// Return the angles of `gate` in the order that ppvm pops them after the qubit.
pub(super) fn angles(gate: &Gate) -> Vec<SSAValue> {
    match gate {
        Gate::Rx(rx) => vec![rx.angle],
        Gate::Ry(ry) => vec![ry.angle],
        Gate::Rz(rz) => vec![rz.angle],
        Gate::U3(u3) => vec![u3.theta, u3.phi, u3.lam],
        _ => Vec::new(),
    }
}
