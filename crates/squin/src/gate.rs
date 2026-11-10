//! Define the unitary gates.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;

use crate::types::SquinType;

/// Name each gate that takes one qubit and no angle.
#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq, HasParser, PrettyPrint)]
pub enum Fixed {
    #[chumsky(format = "x")]
    X,
    #[chumsky(format = "y")]
    Y,
    #[chumsky(format = "z")]
    Z,
    #[chumsky(format = "h")]
    H,
    #[chumsky(format = "s")]
    S,
    #[chumsky(format = "t")]
    T,
    #[chumsky(format = "sqrt_x")]
    SqrtX,
    #[chumsky(format = "sqrt_y")]
    SqrtY,
}

/// Name the axis of a rotation of one qubit.
#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq, HasParser, PrettyPrint)]
pub enum Axis {
    #[chumsky(format = "rx")]
    X,
    #[chumsky(format = "ry")]
    Y,
    #[chumsky(format = "rz")]
    Z,
}

/// Name the Pauli that a controlled gate applies to its target qubit.
#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq, HasParser, PrettyPrint)]
pub enum Controlled {
    #[chumsky(format = "cx")]
    X,
    #[chumsky(format = "cy")]
    Y,
    #[chumsky(format = "cz")]
    Z,
}

/// Apply a unitary gate to wires.
///
/// Each variant fixes its number of qubits and angles in its fields. Angles
/// are in turns, so an angle of 0.5 is a rotation by pi.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
pub enum Gate {
    /// Apply the gate `kind` to one qubit, such as `h %w -> Wire`.
    #[chumsky(format = "{kind} {wire} -> {wire_out:type}")]
    Fixed {
        kind: Fixed,
        wire: SSAValue,
        wire_out: ResultValue,
    },

    /// Rotate one qubit by `angle` about `axis`, such as `rz(%a) %w -> Wire`.
    #[chumsky(format = "{axis}({angle}) {wire} -> {wire_out:type}")]
    Rotation {
        axis: Axis,
        angle: SSAValue,
        wire: SSAValue,
        wire_out: ResultValue,
    },

    /// Apply the general rotation of one qubit with three angles.
    #[chumsky(format = "$u3({theta}, {phi}, {lam}) {wire} -> {wire_out:type}")]
    U3 {
        theta: SSAValue,
        phi: SSAValue,
        lam: SSAValue,
        wire: SSAValue,
        wire_out: ResultValue,
    },

    /// Apply the Pauli `kind` to `target` if `control` is in the one state.
    #[chumsky(format = "{kind} {control}, {target} -> {control_out:type}, {target_out:type}")]
    Controlled {
        kind: Controlled,
        control: SSAValue,
        target: SSAValue,
        control_out: ResultValue,
        target_out: ResultValue,
    },
}
