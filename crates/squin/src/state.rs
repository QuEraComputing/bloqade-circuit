//! Define the statements that create, move and measure qubits.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;

use crate::types::SquinType;

/// Allocate, lend, move, measure and free qubits.
///
/// Every statement consumes its wire and register operands. A statement that
/// keeps a qubit alive returns the next value of that wire or register.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
pub enum State {
    /// Allocate one qubit in the zero state.
    #[chumsky(format = "$alloc -> {wire:type}")]
    Alloc { wire: ResultValue },

    /// End the life of the qubit of `wire`.
    #[chumsky(format = "$free {wire}")]
    Free { wire: SSAValue },

    /// Allocate `size` qubits in the zero state as one register.
    #[chumsky(format = "$alloc_register {size} -> {register:type}")]
    AllocRegister {
        size: SSAValue,
        register: ResultValue,
    },

    /// End the life of every qubit of `register`.
    #[chumsky(format = "$free_register {register}")]
    FreeRegister { register: SSAValue },

    /// Lend the qubit at `index` of `register` to a wire.
    ///
    /// The element stays empty until a `release` consumes `slot`.
    #[chumsky(
        format = "$borrow {register}, {index} -> {register_out:type}, {slot:type}, {wire:type}"
    )]
    Borrow {
        register: SSAValue,
        index: SSAValue,
        register_out: ResultValue,
        slot: ResultValue,
        wire: ResultValue,
    },

    /// Put the qubit of `wire` back into the element that `slot` names.
    ///
    /// The wire must carry the qubit that the `borrow` of `slot` took out.
    #[chumsky(format = "$release {register}, {slot}, {wire} -> {register_out:type}")]
    Release {
        register: SSAValue,
        slot: SSAValue,
        wire: SSAValue,
        register_out: ResultValue,
    },

    /// Put the qubit of `wire` at `index` and return the qubit that was there.
    ///
    /// This is the statement that moves a qubit to a new register position.
    #[chumsky(
        format = "$replace {register}, {index}, {wire} -> {register_out:type}, {wire_out:type}"
    )]
    Replace {
        register: SSAValue,
        index: SSAValue,
        wire: SSAValue,
        register_out: ResultValue,
        wire_out: ResultValue,
    },

    /// Consume `wires` and form a register that holds them in operand order.
    #[chumsky(format = "$pack {wires} -> {register:type}")]
    Pack {
        wires: Vec<SSAValue>,
        register: ResultValue,
    },

    /// Divide `register` into the elements before `index` and the other elements.
    #[chumsky(format = "$split {register}, {index} -> {before:type}, {after:type}")]
    Split {
        register: SSAValue,
        index: SSAValue,
        before: ResultValue,
        after: ResultValue,
    },

    /// Consume two registers and form one register of `first` and then `second`.
    #[chumsky(format = "$join {first}, {second} -> {register:type}")]
    Join {
        first: SSAValue,
        second: SSAValue,
        register: ResultValue,
    },

    /// Return `register` and the number of qubits that it holds.
    #[chumsky(format = "$length {register} -> {register_out:type}, {length:type}")]
    Length {
        register: SSAValue,
        register_out: ResultValue,
        length: ResultValue,
    },

    /// Measure the qubit of `wire` and keep the qubit.
    #[chumsky(format = "$measure {wire} -> {wire_out:type}, {bit:type}")]
    Measure {
        wire: SSAValue,
        wire_out: ResultValue,
        bit: ResultValue,
    },

    /// Measure every qubit of `register` and return the results in element order.
    #[chumsky(format = "$measure_register {register} -> {register_out:type}, {bits:type}")]
    MeasureRegister {
        register: SSAValue,
        register_out: ResultValue,
        bits: ResultValue,
    },

    /// Reset the qubit of `wire` to the zero state.
    #[chumsky(format = "$reset {wire} -> {wire_out:type}")]
    Reset {
        wire: SSAValue,
        wire_out: ResultValue,
    },
}
