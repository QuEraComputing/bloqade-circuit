//! Check the operand types and the result types of each statement.
//!
//! The `lent` count of a register type makes this check enforce two rules. A
//! statement on a whole register requires `lent=0`. A loop body returns each
//! register with the `lent` count that it received.

use kirin::prelude::*;
use kirin_scf::{For, If, StructuredControlFlow};

use super::program::Program;
use super::violation::{Report, Rule};
use crate::bits::BitsOp;
use crate::gate::Gate;
use crate::language::Squin;
use crate::state::State;
use crate::types::{Length, SquinType};

const ANY_REGISTER: SquinType = SquinType::Register {
    len: Length::Any,
    lent: 0,
};

/// Check the types of `statement` and record each mismatch in `report`.
pub(super) fn check(program: Program<'_>, statement: Statement, report: &mut Report) {
    let mut typing = Typing { program, report };
    match program.definition(statement) {
        Squin::State(state) => typing.state(state),
        Squin::Gate(gate) => typing.gate(gate),
        Squin::Bits(bits) => typing.bits(bits),
        Squin::Structured(StructuredControlFlow::If(branch)) => typing.branch(branch),
        Squin::Structured(StructuredControlFlow::For(repeat)) => typing.repeat(repeat),
        _ => {}
    }
}

struct Typing<'a, 'r> {
    program: Program<'a>,
    report: &'r mut Report,
}

impl Typing<'_, '_> {
    fn state(&mut self, state: &State) {
        use SquinType::{Bit, Bits, Int, Register, Slot, Wire};
        match *state {
            State::Alloc { wire } => self.expect(wire, Wire),
            State::Free { wire } => self.expect(wire, Wire),
            State::AllocRegister { size, register } => {
                self.expect(size, Int);
                self.expect(register, ANY_REGISTER);
            }
            State::FreeRegister { register } => self.expect(register, ANY_REGISTER),
            State::Borrow {
                register,
                index,
                register_out,
                slot,
                wire,
            } => {
                self.expect(index, Int);
                self.expect(slot, Slot);
                self.expect(wire, Wire);
                if let Some((len, lent)) = self.register(register) {
                    let lent = lent + 1;
                    self.exact(register_out, Register { len, lent });
                }
            }
            State::Release {
                register,
                slot,
                wire,
                register_out,
            } => {
                self.expect(slot, Slot);
                self.expect(wire, Wire);
                match self.register(register) {
                    Some((_, 0)) => self.fail(register, "a register with an empty element"),
                    Some((len, lent)) => {
                        let lent = lent - 1;
                        self.exact(register_out, Register { len, lent });
                    }
                    None => {}
                }
            }
            State::Replace {
                register,
                index,
                wire,
                register_out,
                wire_out,
            } => {
                self.expect(register, ANY_REGISTER);
                self.expect(index, Int);
                self.expect(wire, Wire);
                self.exact(register_out, self.program.ty(register));
                self.expect(wire_out, Wire);
            }
            State::Pack {
                ref wires,
                register,
            } => {
                self.each(wires.iter().copied(), Wire);
                self.covers(register, SquinType::register(count(wires)));
            }
            State::Split {
                register,
                index,
                before,
                after,
            } => {
                self.expect(register, ANY_REGISTER);
                self.expect(index, Int);
                self.expect(before, ANY_REGISTER);
                self.expect(after, ANY_REGISTER);
            }
            State::Join {
                first,
                second,
                register,
            } => {
                self.expect(first, ANY_REGISTER);
                self.expect(second, ANY_REGISTER);
                self.expect(register, ANY_REGISTER);
            }
            State::Length {
                register,
                register_out,
                length,
            } => {
                self.register(register);
                self.exact(register_out, self.program.ty(register));
                self.expect(length, Int);
            }
            State::Measure {
                wire,
                wire_out,
                bit,
            } => {
                self.expect(wire, Wire);
                self.expect(wire_out, Wire);
                self.expect(bit, Bit);
            }
            State::MeasureRegister {
                register,
                register_out,
                bits,
            } => {
                self.expect(register, ANY_REGISTER);
                self.exact(register_out, self.program.ty(register));
                if let Some((len, _)) = self.register(register) {
                    self.exact(bits, Bits(len));
                }
            }
            State::Reset { wire, wire_out } => {
                self.expect(wire, Wire);
                self.expect(wire_out, Wire);
            }
        }
    }

    fn gate(&mut self, gate: &Gate) {
        use SquinType::{Float, Wire};
        match *gate {
            Gate::Fixed { wire, wire_out, .. } => {
                self.expect(wire, Wire);
                self.expect(wire_out, Wire);
            }
            Gate::Rotation {
                angle,
                wire,
                wire_out,
                ..
            } => {
                self.expect(angle, Float);
                self.expect(wire, Wire);
                self.expect(wire_out, Wire);
            }
            Gate::U3 {
                theta,
                phi,
                lam,
                wire,
                wire_out,
            } => {
                self.each([theta, phi, lam], Float);
                self.expect(wire, Wire);
                self.expect(wire_out, Wire);
            }
            Gate::Controlled {
                control,
                target,
                control_out,
                target_out,
                ..
            } => {
                self.each([control, target], Wire);
                self.each([control_out, target_out], Wire);
            }
        }
    }

    fn bits(&mut self, bits: &BitsOp) {
        use SquinType::{Bit, Bits, Int};
        match *bits {
            BitsOp::Pack { ref bits, result } => {
                self.each(bits.iter().copied(), Bit);
                self.covers(result, Bits(count(bits)));
            }
            BitsOp::Get { bits, index, bit } => {
                self.expect(bits, Bits(Length::Any));
                self.expect(index, Int);
                self.expect(bit, Bit);
            }
            BitsOp::Length { bits, length } => {
                self.expect(bits, Bits(Length::Any));
                self.expect(length, Int);
            }
        }
    }

    /// Check that each arm of `branch` yields the types of the results.
    fn branch(&mut self, branch: &If<SquinType>) {
        self.expect(branch.condition(), SquinType::Bool);
        for arm in [branch.then_block(), branch.else_block()] {
            self.flows(&self.program.yields(arm), branch.results());
        }
    }

    /// Check that the loop body receives and yields the types that it carries.
    fn repeat(&mut self, repeat: &For<SquinType>) {
        self.each(
            [repeat.start(), repeat.end(), repeat.step()],
            SquinType::Int,
        );
        let carried: Vec<SSAValue> = self.program.arguments(repeat.body()).skip(1).collect();
        self.flows(repeat.init_args(), &carried);
        self.flows(&self.program.yields(repeat.body()), &carried);
        self.flows(&carried, repeat.results());
    }

    /// Require each value of `sources` to fit the type of its `targets` value.
    fn flows<S, T>(&mut self, sources: &[S], targets: &[T])
    where
        S: Copy + Into<SSAValue>,
        T: Copy + Into<SSAValue>,
    {
        if sources.len() != targets.len() {
            let (found, expected) = (sources.len(), targets.len());
            let message = format!("A block passes on {found} values where {expected} must arrive.");
            return self.report.add(Rule::Type, message);
        }
        for (source, target) in sources.iter().zip(targets) {
            self.expect(*source, self.program.ty(*target));
        }
    }

    /// Require the type of `value` to be `expected` or one of its subtypes.
    fn expect(&mut self, value: impl Into<SSAValue>, expected: SquinType) {
        let value = value.into();
        if !self.program.ty(value).is_subseteq(&expected) {
            self.fail(value, &expected.to_string());
        }
    }

    /// Require the type of each value of `values` to be `expected` or a subtype.
    fn each<V: Into<SSAValue>>(
        &mut self,
        values: impl IntoIterator<Item = V>,
        expected: SquinType,
    ) {
        for value in values {
            self.expect(value, expected);
        }
    }

    /// Require the type of `value` to be exactly `expected`.
    fn exact(&mut self, value: impl Into<SSAValue>, expected: SquinType) {
        let value = value.into();
        if self.program.ty(value) != expected {
            self.fail(value, &expected.to_string());
        }
    }

    /// Require the declared type of `value` to include the type `computed`.
    fn covers(&mut self, value: impl Into<SSAValue>, computed: SquinType) {
        let value = value.into();
        if !computed.is_subseteq(&self.program.ty(value)) {
            self.fail(value, &computed.to_string());
        }
    }

    /// Return the length and the lent count of `value` if it is a register.
    fn register(&mut self, value: SSAValue) -> Option<(Length, u32)> {
        match self.program.ty(value) {
            SquinType::Register { len, lent } => Some((len, lent)),
            _ => {
                self.fail(value, "a register");
                None
            }
        }
    }

    fn fail(&mut self, value: SSAValue, expected: &str) {
        let (name, found) = (self.program.name(value), self.program.ty(value));
        let message = format!("{name} has the type {found}, and its statement needs {expected}.");
        self.report.add(Rule::Type, message);
    }
}

/// Return the known length of a pack of `values`.
fn count(values: &[SSAValue]) -> Length {
    Length::Known(values.len() as u64)
}
