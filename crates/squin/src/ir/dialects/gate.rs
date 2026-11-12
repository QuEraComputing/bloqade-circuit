//! Define the gate dialect, with one statement for each unitary gate.
//!
//! The gates of one family have the same fields. A macro writes the struct of
//! each gate of a family. Angles are in turns, so an angle of 0.5 is a
//! rotation by pi.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use std::marker::PhantomData;

use kirin::prelude::*;
use smallvec::smallvec;

use crate::ir::macros::delegate;
use crate::ir::traits::{Pairs, Threads};
use crate::ir::types::QuantumTypes;

/// Define each gate that takes one qubit and no angle.
macro_rules! single_qubit_gates {
    ($($(#[$doc:meta])* $name:ident = $format:tt;)+) => {$(
        $(#[$doc])*
        #[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
        #[kirin(pure, builders, type = Ty)]
        #[chumsky(format = $format)]
        pub struct $name<Ty: QuantumTypes> {
            pub wire: SSAValue,
            #[kirin(type = Ty::wire())]
            pub wire_out: ResultValue,
            #[kirin(default)]
            pub marker: PhantomData<Ty>,
        }

        impl<Ty: QuantumTypes> Threads for $name<Ty> {
            fn threads(&self) -> Pairs {
                smallvec![(self.wire, self.wire_out)]
            }
        }

    )+};
}

/// Define each rotation of one qubit by one angle.
macro_rules! rotation_gates {
    ($($(#[$doc:meta])* $name:ident = $format:tt;)+) => {$(
        $(#[$doc])*
        #[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
        #[kirin(pure, builders, type = Ty)]
        #[chumsky(format = $format)]
        pub struct $name<Ty: QuantumTypes> {
            pub angle: SSAValue,
            pub wire: SSAValue,
            #[kirin(type = Ty::wire())]
            pub wire_out: ResultValue,
            #[kirin(default)]
            pub marker: PhantomData<Ty>,
        }

        impl<Ty: QuantumTypes> Threads for $name<Ty> {
            fn threads(&self) -> Pairs {
                smallvec![(self.wire, self.wire_out)]
            }
        }

    )+};
}

/// Define each gate that applies a Pauli to `target` if `control` is in the one state.
macro_rules! controlled_gates {
    ($($(#[$doc:meta])* $name:ident = $format:tt;)+) => {$(
        $(#[$doc])*
        #[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
        #[kirin(pure, builders, type = Ty)]
        #[chumsky(format = $format)]
        pub struct $name<Ty: QuantumTypes> {
            pub control: SSAValue,
            pub target: SSAValue,
            #[kirin(type = Ty::wire())]
            pub control_out: ResultValue,
            #[kirin(type = Ty::wire())]
            pub target_out: ResultValue,
            #[kirin(default)]
            pub marker: PhantomData<Ty>,
        }

        impl<Ty: QuantumTypes> Threads for $name<Ty> {
            fn threads(&self) -> Pairs {
                smallvec![(self.control, self.control_out), (self.target, self.target_out)]
            }
        }

    )+};
}

single_qubit_gates! {
    /// Apply the Pauli X gate.
    X = "$x {wire}";
    /// Apply the Pauli Y gate.
    Y = "$y {wire}";
    /// Apply the Pauli Z gate.
    Z = "$z {wire}";
    /// Apply the Hadamard gate.
    H = "$h {wire}";
    /// Apply the S gate, which is a quarter turn about Z.
    S = "$s {wire}";
    /// Apply the inverse of the S gate.
    SDag = "$s_dag {wire}";
    /// Apply the T gate, which is an eighth of a turn about Z.
    T = "$t {wire}";
    /// Apply the inverse of the T gate.
    TDag = "$t_dag {wire}";
    /// Apply the square root of the Pauli X gate.
    SqrtX = "$sqrt_x {wire}";
    /// Apply the inverse of the square root of the Pauli X gate.
    SqrtXDag = "$sqrt_x_dag {wire}";
    /// Apply the square root of the Pauli Y gate.
    SqrtY = "$sqrt_y {wire}";
    /// Apply the inverse of the square root of the Pauli Y gate.
    SqrtYDag = "$sqrt_y_dag {wire}";
}

rotation_gates! {
    /// Rotate one qubit by `angle` about the X axis.
    Rx = "$rx({angle}) {wire}";
    /// Rotate one qubit by `angle` about the Y axis.
    Ry = "$ry({angle}) {wire}";
    /// Rotate one qubit by `angle` about the Z axis.
    Rz = "$rz({angle}) {wire}";
}

controlled_gates! {
    /// Apply the Pauli X gate to `target` if `control` is in the one state.
    CX = "$cx {control}, {target}";
    /// Apply the Pauli Y gate to `target` if `control` is in the one state.
    CY = "$cy {control}, {target}";
    /// Apply the Pauli Z gate to `target` if `control` is in the one state.
    CZ = "$cz {control}, {target}";
}

/// Apply the general rotation of one qubit with three angles.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = Ty)]
#[chumsky(format = "$u3({theta}, {phi}, {lam}) {wire}")]
pub struct U3<Ty: QuantumTypes> {
    pub theta: SSAValue,
    pub phi: SSAValue,
    pub lam: SSAValue,
    pub wire: SSAValue,
    #[kirin(type = Ty::wire())]
    pub wire_out: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

impl<Ty: QuantumTypes> Threads for U3<Ty> {
    fn threads(&self) -> Pairs {
        smallvec![(self.wire, self.wire_out)]
    }
}

/// Hold one statement of the gate dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[wraps]
#[kirin(pure, builders, type = Ty)]
pub enum Gate<Ty: QuantumTypes> {
    X(X<Ty>),
    Y(Y<Ty>),
    Z(Z<Ty>),
    H(H<Ty>),
    S(S<Ty>),
    SDag(SDag<Ty>),
    T(T<Ty>),
    TDag(TDag<Ty>),
    SqrtX(SqrtX<Ty>),
    SqrtXDag(SqrtXDag<Ty>),
    SqrtY(SqrtY<Ty>),
    SqrtYDag(SqrtYDag<Ty>),
    Rx(Rx<Ty>),
    Ry(Ry<Ty>),
    Rz(Rz<Ty>),
    U3(U3<Ty>),
    CX(CX<Ty>),
    CY(CY<Ty>),
    CZ(CZ<Ty>),
}

delegate!(generic Gate {
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

/// Call the macro `$callback` with every gate and the names of its angle fields.
///
/// The verifier and the analyses use this list to write the rule of each gate.
/// A gate with no entry here has no rule, and the crate does not compile.
macro_rules! for_each_gate {
    ($callback:ident) => {
        $callback! {
            X; Y; Z; H; S; SDag; T; TDag; SqrtX; SqrtXDag; SqrtY; SqrtYDag;
            Rx(angle); Ry(angle); Rz(angle);
            U3(theta, phi, lam);
            CX; CY; CZ;
        }
    };
}

pub(crate) use for_each_gate;
