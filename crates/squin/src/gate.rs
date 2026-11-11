//! Define the unitary gates, with one statement for each gate.
//!
//! The gates of one family have the same fields and the same rules. A macro
//! writes the struct and the rules of each gate of a family. Angles are in
//! turns, so an angle of 0.5 is a rotation by pi.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;
use smallvec::smallvec;

use crate::macros::{delegate, plain};
use crate::run::{Backend, Execute, Failure, Machine, Operation, Value};
use crate::threads::{Pairs, Threads};
use crate::types::SquinType;
use crate::verify::{Structure, Typed, Typing};

/// Define each gate that takes one qubit and no angle.
macro_rules! single_qubit_gates {
    ($($(#[$doc:meta])* $name:ident = $format:tt;)+) => {$(
        $(#[$doc])*
        #[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
        #[kirin(pure, builders, type = SquinType)]
        #[chumsky(format = $format)]
        pub struct $name {
            pub wire: SSAValue,
            pub wire_out: ResultValue,
        }

        impl Threads for $name {
            fn threads(&self) -> Pairs {
                smallvec![(self.wire, self.wire_out)]
            }
        }

        impl Typed for $name {
            fn check(&self, typing: &mut Typing<'_, '_>) {
                check(typing, &self.threads(), &[]);
            }
        }

        impl Execute for $name {
            fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
                apply(machine, Operation::$name, &self.threads())
            }
        }

        plain!(Structure, for $name);
    )+};
}

/// Define each rotation of one qubit by one angle.
macro_rules! rotation_gates {
    ($($(#[$doc:meta])* $name:ident = $format:tt;)+) => {$(
        $(#[$doc])*
        #[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
        #[kirin(pure, builders, type = SquinType)]
        #[chumsky(format = $format)]
        pub struct $name {
            pub angle: SSAValue,
            pub wire: SSAValue,
            pub wire_out: ResultValue,
        }

        impl Threads for $name {
            fn threads(&self) -> Pairs {
                smallvec![(self.wire, self.wire_out)]
            }
        }

        impl Typed for $name {
            fn check(&self, typing: &mut Typing<'_, '_>) {
                check(typing, &self.threads(), &[self.angle]);
            }
        }

        impl Execute for $name {
            fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
                let angle = machine.float(self.angle)?;
                apply(machine, Operation::$name(angle), &self.threads())
            }
        }

        plain!(Structure, for $name);
    )+};
}

/// Define each gate that applies a Pauli to `target` if `control` is in the one state.
macro_rules! controlled_gates {
    ($($(#[$doc:meta])* $name:ident = $format:tt;)+) => {$(
        $(#[$doc])*
        #[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
        #[kirin(pure, builders, type = SquinType)]
        #[chumsky(format = $format)]
        pub struct $name {
            pub control: SSAValue,
            pub target: SSAValue,
            pub control_out: ResultValue,
            pub target_out: ResultValue,
        }

        impl Threads for $name {
            fn threads(&self) -> Pairs {
                smallvec![(self.control, self.control_out), (self.target, self.target_out)]
            }
        }

        impl Typed for $name {
            fn check(&self, typing: &mut Typing<'_, '_>) {
                check(typing, &self.threads(), &[]);
            }
        }

        impl Execute for $name {
            fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
                apply(machine, Operation::$name, &self.threads())
            }
        }

        plain!(Structure, for $name);
    )+};
}

single_qubit_gates! {
    /// Apply the Pauli X gate.
    X = "$x {wire} -> {wire_out:type}";
    /// Apply the Pauli Y gate.
    Y = "$y {wire} -> {wire_out:type}";
    /// Apply the Pauli Z gate.
    Z = "$z {wire} -> {wire_out:type}";
    /// Apply the Hadamard gate.
    H = "$h {wire} -> {wire_out:type}";
    /// Apply the S gate, which is a quarter turn about Z.
    S = "$s {wire} -> {wire_out:type}";
    /// Apply the inverse of the S gate.
    SDag = "$s_dag {wire} -> {wire_out:type}";
    /// Apply the T gate, which is an eighth of a turn about Z.
    T = "$t {wire} -> {wire_out:type}";
    /// Apply the inverse of the T gate.
    TDag = "$t_dag {wire} -> {wire_out:type}";
    /// Apply the square root of the Pauli X gate.
    SqrtX = "$sqrt_x {wire} -> {wire_out:type}";
    /// Apply the inverse of the square root of the Pauli X gate.
    SqrtXDag = "$sqrt_x_dag {wire} -> {wire_out:type}";
    /// Apply the square root of the Pauli Y gate.
    SqrtY = "$sqrt_y {wire} -> {wire_out:type}";
    /// Apply the inverse of the square root of the Pauli Y gate.
    SqrtYDag = "$sqrt_y_dag {wire} -> {wire_out:type}";
}

rotation_gates! {
    /// Rotate one qubit by `angle` about the X axis.
    Rx = "$rx({angle}) {wire} -> {wire_out:type}";
    /// Rotate one qubit by `angle` about the Y axis.
    Ry = "$ry({angle}) {wire} -> {wire_out:type}";
    /// Rotate one qubit by `angle` about the Z axis.
    Rz = "$rz({angle}) {wire} -> {wire_out:type}";
}

controlled_gates! {
    /// Apply the Pauli X gate to `target` if `control` is in the one state.
    CX = "$cx {control}, {target} -> {control_out:type}, {target_out:type}";
    /// Apply the Pauli Y gate to `target` if `control` is in the one state.
    CY = "$cy {control}, {target} -> {control_out:type}, {target_out:type}";
    /// Apply the Pauli Z gate to `target` if `control` is in the one state.
    CZ = "$cz {control}, {target} -> {control_out:type}, {target_out:type}";
}

/// Apply the general rotation of one qubit with three angles.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$u3({theta}, {phi}, {lam}) {wire} -> {wire_out:type}")]
pub struct U3 {
    pub theta: SSAValue,
    pub phi: SSAValue,
    pub lam: SSAValue,
    pub wire: SSAValue,
    pub wire_out: ResultValue,
}

impl Threads for U3 {
    fn threads(&self) -> Pairs {
        smallvec![(self.wire, self.wire_out)]
    }
}

impl Typed for U3 {
    fn check(&self, typing: &mut Typing<'_, '_>) {
        check(typing, &self.threads(), &[self.theta, self.phi, self.lam]);
    }
}

impl Execute for U3 {
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        let theta = machine.float(self.theta)?;
        let phi = machine.float(self.phi)?;
        let lam = machine.float(self.lam)?;
        apply(machine, Operation::U3(theta, phi, lam), &self.threads())
    }
}

plain!(Structure, for U3);

/// Hold one statement of the gate dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[wraps]
#[kirin(pure, builders, type = SquinType)]
pub enum Gate {
    X(X),
    Y(Y),
    Z(Z),
    H(H),
    S(S),
    SDag(SDag),
    T(T),
    TDag(TDag),
    SqrtX(SqrtX),
    SqrtXDag(SqrtXDag),
    SqrtY(SqrtY),
    SqrtYDag(SqrtYDag),
    Rx(Rx),
    Ry(Ry),
    Rz(Rz),
    U3(U3),
    CX(CX),
    CY(CY),
    CZ(CZ),
}

delegate!(Gate {
    X,
    Y,
    Z,
    H,
    S,
    SDag,
    T,
    TDag,
    SqrtX,
    SqrtXDag,
    SqrtY,
    SqrtYDag,
    Rx,
    Ry,
    Rz,
    U3,
    CX,
    CY,
    CZ,
});

impl Gate {
    /// Check whether `self` and then `next` on the same qubits are the identity.
    pub fn cancels(&self, next: &Gate) -> bool {
        use Gate::{CX, CY, CZ, H, S, SDag, SqrtX, SqrtXDag, SqrtY, SqrtYDag, T, TDag, X, Y, Z};
        matches!(
            (self, next),
            (X(_), X(_))
                | (Y(_), Y(_))
                | (Z(_), Z(_))
                | (H(_), H(_))
                | (CX(_), CX(_))
                | (CY(_), CY(_))
                | (CZ(_), CZ(_))
                | (S(_), SDag(_))
                | (SDag(_), S(_))
                | (T(_), TDag(_))
                | (TDag(_), T(_))
                | (SqrtX(_), SqrtXDag(_))
                | (SqrtXDag(_), SqrtX(_))
                | (SqrtY(_), SqrtYDag(_))
                | (SqrtYDag(_), SqrtY(_))
        )
    }

    /// Return the angle and the input wire of a rotation about one axis.
    pub fn rotation(&self) -> Option<(SSAValue, SSAValue)> {
        match self {
            Gate::Rx(Rx { angle, wire, .. })
            | Gate::Ry(Ry { angle, wire, .. })
            | Gate::Rz(Rz { angle, wire, .. }) => Some((*angle, *wire)),
            _ => None,
        }
    }
}

/// Require each wire of `threads` to be a `Wire` and each angle to be a `Float`.
fn check(typing: &mut Typing<'_, '_>, threads: &Pairs, angles: &[SSAValue]) {
    typing.each(angles.iter().copied(), SquinType::Float);
    for (wire, wire_out) in threads {
        typing.expect(*wire, SquinType::Wire);
        typing.expect(*wire_out, SquinType::Wire);
    }
}

/// Hand `operation` to the backend with the qubits of the input wires of `threads`.
fn apply<B: Backend>(
    machine: &mut Machine<'_, B>,
    operation: Operation,
    threads: &Pairs,
) -> Result<(), Failure> {
    let qubits = threads.iter().map(|(wire, _)| machine.wire(*wire));
    let qubits = qubits.collect::<Result<Vec<_>, _>>()?;
    machine.backend().gate(operation, &qubits)?;
    for ((_, wire_out), qubit) in threads.iter().zip(qubits) {
        machine.write(*wire_out, Value::Wire(qubit));
    }
    Ok(())
}
