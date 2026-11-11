//! Check the operand types and the result types of each statement.
//!
//! The `lent` count of a register type makes this check enforce two rules. A
//! statement on a whole register requires `lent=0`. A loop body returns each
//! register with the `lent` count that it received.

use kirin::prelude::*;

use super::program::Program;
use super::violation::{Report, Violation};
use crate::types::{Length, SquinType};

/// State the types that a statement needs for its operands and results.
pub trait Typed {
    /// Check the types of the statement and record each mismatch in `typing`.
    ///
    /// The default is for a statement that accepts every type.
    fn check(&self, _typing: &mut Typing<'_, '_>) {}
}

/// Give a type rule the types of the program and collect its findings.
pub struct Typing<'a, 'r> {
    program: Program<'a>,
    report: &'r mut Report,
}

impl<'a, 'r> Typing<'a, 'r> {
    pub(super) fn new(program: Program<'a>, report: &'r mut Report) -> Self {
        Self { program, report }
    }

    /// Return the type of `value`.
    pub fn ty(&self, value: impl Into<SSAValue>) -> SquinType {
        self.program.ty(value)
    }

    /// Return the values that the terminator of `block` passes on.
    pub fn yields(&self, block: Block) -> Vec<SSAValue> {
        self.program.yields(block)
    }

    /// Return the arguments of `block`.
    pub fn arguments(&self, block: Block) -> Vec<SSAValue> {
        self.program.arguments(block).collect()
    }

    /// Require the type of `value` to be `expected` or one of its subtypes.
    pub fn expect(&mut self, value: impl Into<SSAValue>, expected: SquinType) {
        let value = value.into();
        if !self.ty(value).is_subseteq(&expected) {
            self.fail(value, expected.to_string());
        }
    }

    /// Require the type of each value of `values` to be `expected` or a subtype.
    pub fn each<V: Into<SSAValue>>(
        &mut self,
        values: impl IntoIterator<Item = V>,
        expected: SquinType,
    ) {
        for value in values {
            self.expect(value, expected);
        }
    }

    /// Require the type of `value` to be exactly `expected`.
    pub fn exact(&mut self, value: impl Into<SSAValue>, expected: SquinType) {
        let value = value.into();
        if self.ty(value) != expected {
            self.fail(value, expected.to_string());
        }
    }

    /// Require the declared type of `value` to include the type `computed`.
    pub fn covers(&mut self, value: impl Into<SSAValue>, computed: SquinType) {
        let value = value.into();
        if !computed.is_subseteq(&self.ty(value)) {
            self.fail(value, computed.to_string());
        }
    }

    /// Require `value` to be a register with every element in place.
    pub fn whole(&mut self, value: impl Into<SSAValue>) {
        self.expect(value, SquinType::register(Length::Any));
    }

    /// Return the length and the lent count of `value` if it is a register.
    pub fn register(&mut self, value: SSAValue) -> Option<(Length, u32)> {
        match self.ty(value) {
            SquinType::Register { len, lent } => Some((len, lent)),
            _ => {
                self.fail(value, "a register");
                None
            }
        }
    }

    /// Require each value of `sources` to fit the type of its `targets` value.
    pub fn flows<S, T>(&mut self, sources: &[S], targets: &[T])
    where
        S: Copy + Into<SSAValue>,
        T: Copy + Into<SSAValue>,
    {
        if sources.len() != targets.len() {
            let (found, expected) = (sources.len(), targets.len());
            return self.report.add(Violation::Arity { expected, found });
        }
        for (source, target) in sources.iter().zip(targets) {
            self.expect(*source, self.ty(*target));
        }
    }

    /// Record that `value` has another type than the type `expected` names.
    pub fn fail(&mut self, value: SSAValue, expected: impl Into<String>) {
        let (found, expected) = (self.ty(value), expected.into());
        let value = self.program.named(value);
        self.report.add(Violation::Type {
            value,
            found,
            expected,
        });
    }
}
