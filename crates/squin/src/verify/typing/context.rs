//! Define the context that a type rule reads types from and reports to.

use kirin::prelude::*;

use crate::ir::types::{Length, SquinType};
use crate::verify::program::Program;
use crate::verify::violation::{Report, Violation};

/// Give a type rule the types of the program and collect its findings.
///
/// The verifier implements this trait. A statement uses the provided methods,
/// which build on the required ones.
pub trait TypeCheck {
    /// Return the type of `value`.
    fn ty(&self, value: SSAValue) -> SquinType;

    /// Return the values that the terminator of `block` passes on.
    fn yields(&self, block: Block) -> Vec<SSAValue>;

    /// Return the arguments of `block`.
    fn arguments(&self, block: Block) -> Vec<SSAValue>;

    /// Return the blocks of the function body `body`, with the entry block first.
    fn body_blocks(&self, body: CFG) -> Vec<Block>;

    /// Record that `value` has another type than the type `expected` names.
    fn report_type(&mut self, value: SSAValue, expected: String);

    /// Record that a block passes on `found` values where `expected` must arrive.
    fn report_arity(&mut self, expected: usize, found: usize);

    /// Record that `value` has another type than the type `expected` names.
    fn fail(&mut self, value: impl Into<SSAValue>, expected: impl Into<String>) {
        self.report_type(value.into(), expected.into());
    }

    /// Return whether `found` equals `expected`, and record a violation if it does not.
    fn arity(&mut self, expected: usize, found: usize) -> bool {
        if expected != found {
            self.report_arity(expected, found);
        }
        expected == found
    }

    /// Require `value` to fit `expected` and keep its ownership rule.
    fn expect(&mut self, value: impl Into<SSAValue>, expected: SquinType) {
        let value = value.into();
        if !fits(self.ty(value), expected) {
            self.fail(value, expected.to_string());
        }
    }

    /// Require each value to fit `expected` and keep its ownership rule.
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
        if self.ty(value) != expected {
            self.fail(value, expected.to_string());
        }
    }

    /// Require `computed` to fit the declared type of `value` and keep its ownership rule.
    fn covers(&mut self, value: impl Into<SSAValue>, computed: SquinType) {
        let value = value.into();
        if !fits(computed, self.ty(value)) {
            self.fail(value, computed.to_string());
        }
    }

    /// Require `value` to be a register with every element in place.
    fn whole(&mut self, value: impl Into<SSAValue>) {
        self.expect(value, SquinType::register(Length::Any));
    }

    /// Return the length and the lent count of `value` if it is a register.
    fn register(&mut self, value: impl Into<SSAValue>) -> Option<(Length, u32)> {
        let value = value.into();
        match self.ty(value) {
            SquinType::Register { len, lent } => Some((len, lent)),
            _ => {
                self.fail(value, "a register");
                None
            }
        }
    }

    /// Require each value of `sources` to fit the type of its `targets` value.
    fn flows<S, T>(&mut self, sources: &[S], targets: &[T])
    where
        S: Copy + Into<SSAValue>,
        T: Copy + Into<SSAValue>,
    {
        if !self.arity(targets.len(), sources.len()) {
            return;
        }
        for (source, target) in sources.iter().zip(targets) {
            let expected = self.ty((*target).into());
            self.expect(*source, expected);
        }
    }

    /// Check the entry arguments and the return values against the function signature.
    fn function(&mut self, body: CFG, signature: &Signature<SquinType>) {
        let blocks = self.body_blocks(body);
        let Some(&entry) = blocks.first() else {
            self.arity(1, 0);
            return;
        };
        let arguments = self.arguments(entry);
        if self.arity(signature.params().len(), arguments.len()) {
            for (argument, expected) in arguments.iter().zip(signature.params()) {
                self.exact(*argument, *expected);
            }
        }
        for block in blocks {
            let returned = self.yields(block);
            if self.arity(1, returned.len()) {
                self.expect(returned[0], *signature.ret());
            }
        }
    }
}

/// Check whether execution can pass a value from `source` to `target`.
fn fits(source: SquinType, target: SquinType) -> bool {
    // Bottom describes a value that execution cannot produce.
    // The evaluator copies non-linear values, so a type change must preserve the ownership rule.
    source != SquinType::Bottom
        && source.is_linear() == target.is_linear()
        && source.is_subseteq(&target)
}

/// Give the type rules of the statements the types of the program, and collect their findings.
pub(crate) struct Typing<'a, 'r> {
    program: Program<'a>,
    report: &'r mut Report,
}

impl<'a, 'r> Typing<'a, 'r> {
    pub(crate) fn new(program: Program<'a>, report: &'r mut Report) -> Self {
        Self { program, report }
    }

    /// Check the bounds that a declared register type must satisfy.
    pub(crate) fn validate_type(&mut self, value: SSAValue) {
        if let SquinType::Register {
            len: Length::Known(length),
            lent,
        } = self.ty(value)
            && u64::from(lent) > length
        {
            self.fail(
                value,
                format!("a register with at most {length} open borrows"),
            );
        }
    }
}

impl TypeCheck for Typing<'_, '_> {
    fn ty(&self, value: SSAValue) -> SquinType {
        self.program.ty(value)
    }

    fn yields(&self, block: Block) -> Vec<SSAValue> {
        self.program.yields(block)
    }

    fn arguments(&self, block: Block) -> Vec<SSAValue> {
        self.program.arguments(block).collect()
    }

    fn body_blocks(&self, body: CFG) -> Vec<Block> {
        self.program.cfg_blocks(body).collect()
    }

    fn report_type(&mut self, value: SSAValue, expected: String) {
        let found = self.ty(value);
        let value = self.program.named(value);
        self.report.add(Violation::Type {
            value,
            found,
            expected,
        });
    }

    fn report_arity(&mut self, expected: usize, found: usize) {
        self.report.add(Violation::Arity { expected, found });
    }
}
