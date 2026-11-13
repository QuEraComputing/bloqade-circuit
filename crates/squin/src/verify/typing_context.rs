//! Collect type violations while the verifier checks a program.

use kirin::prelude::*;

use super::TypeCheck;
use super::program::Program;
use super::violation::{Report, Violation};
use crate::ir::types::{Length, SquinType};

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

    fn ports(&self, graph: DiGraph) -> Vec<SSAValue> {
        self.program.ports(graph)
    }

    fn graph_yields(&self, graph: DiGraph) -> Vec<SSAValue> {
        self.program.graph_yields(graph)
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
