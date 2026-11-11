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

use crate::dialect::macros::{delegate, plain};
use crate::dialect::semantics::{Backend, Failure, Operation, Value};
use crate::dialect::traits::{Evaluator, Execute, Pairs, Structure, Threads, TypeCheck, Typed};
use crate::dialect::types::SquinType;

mod macros;

use macros::{controlled_gates, rotation_gates, single_qubit_gates};

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
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        check(typing, &self.threads(), &[self.theta, self.phi, self.lam]);
    }
}

impl Execute for U3 {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
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

/// Require each wire of `threads` to be a `Wire` and each angle to be a `Float`.
fn check(typing: &mut impl TypeCheck, threads: &Pairs, angles: &[SSAValue]) {
    typing.each(angles.iter().copied(), SquinType::Float);
    for (wire, wire_out) in threads {
        typing.expect(*wire, SquinType::Wire);
        typing.expect(*wire_out, SquinType::Wire);
    }
}

/// Hand `operation` to the backend with the qubits of the input wires of `threads`.
fn apply<E: Evaluator>(
    machine: &mut E,
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
