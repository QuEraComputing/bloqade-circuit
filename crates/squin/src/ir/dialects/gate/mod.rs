//! Define the gate dialect, with one statement for each unitary gate.
//!
//! The gates of one family have the same fields. A macro writes the struct of
//! each gate of a family. Angles are in turns, so an angle of 0.5 is a
//! rotation by pi.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;
use kirin_interpreter::Interpretable;
use smallvec::smallvec;

use crate::ir::macros::delegate;
use crate::ir::traits::{Pairs, Threads};
use crate::ir::types::SquinType;

mod families;

use families::{controlled_gates, rotation_gates, single_qubit_gates};

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
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$u3({theta}, {phi}, {lam}) {wire}")]
pub struct U3 {
    pub theta: SSAValue,
    pub phi: SSAValue,
    pub lam: SSAValue,
    pub wire: SSAValue,
    #[kirin(type = SquinType::Wire)]
    pub wire_out: ResultValue,
}

impl Threads for U3 {
    fn threads(&self) -> Pairs {
        smallvec![(self.wire, self.wire_out)]
    }
}

/// Hold one statement of the gate dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint, Interpretable)]
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
