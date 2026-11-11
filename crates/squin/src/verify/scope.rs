//! Check that every operand has a visible definition before its use.

use std::collections::HashSet;

use kirin::prelude::*;
use kirin_scf::StructuredControlFlow;

use super::program::Program;
use super::violation::{Report, Violation};
use crate::ir::Squin;

pub(super) fn check(program: Program<'_>, root: Block, report: &mut Report) {
    block(program, root, true, &mut HashSet::new(), report);
}

fn block(
    program: Program<'_>,
    current: Block,
    function: bool,
    visible: &mut HashSet<SSAValue>,
    report: &mut Report,
) {
    let mut local: Vec<_> = program.arguments(current).collect();
    visible.extend(local.iter().copied());
    for statement in program.body(current) {
        for operand in program.operands(statement) {
            if !visible.contains(&operand) {
                report.add(Violation::OutOfScope {
                    value: program.named(operand),
                });
            }
        }
        for child in program.children(statement) {
            block(program, child, false, visible, report);
        }
        let results: Vec<_> = program.results(statement).collect();
        visible.extend(results.iter().copied());
        local.extend(results);
    }
    let terminator = program
        .terminator(current)
        .map(|last| program.definition(last));
    let valid = matches!((function, terminator), (true, Some(Squin::Return(_))))
        || matches!(
            (function, terminator),
            (
                false,
                Some(Squin::Structured(StructuredControlFlow::Yield(_)))
            )
        );
    if !valid {
        report.add(Violation::Terminator {
            block: current,
            expected: if function { "ret" } else { "yield" },
        });
    }
    for value in local {
        visible.remove(&value);
    }
}
