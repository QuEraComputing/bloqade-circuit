//! Check the operand types and the result types of each statement.
//!
//! The `lent` count of a register type makes this check enforce two rules. A
//! statement on a whole register requires `lent=0`. A loop body returns each
//! register with the `lent` count that it received.

use kirin::prelude::*;

use super::program::Program;
use super::violation::{Report, Violation};
use crate::ir::contexts::TypeCheck;
use crate::ir::types::{Length, SquinType};

/// Give the type rules of the statements the types of the program, and collect their findings.
pub(super) struct Typing<'a, 'r> {
    program: Program<'a>,
    report: &'r mut Report,
}

impl<'a, 'r> Typing<'a, 'r> {
    pub(super) fn new(program: Program<'a>, report: &'r mut Report) -> Self {
        Self { program, report }
    }

    /// Check the bounds that a declared register type must satisfy.
    pub(super) fn validate_type(&mut self, value: SSAValue) {
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
