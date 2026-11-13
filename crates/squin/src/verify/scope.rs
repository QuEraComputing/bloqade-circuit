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

/// Check the nodes and the yields of `current` against the values that they can see.
///
/// A node can read a port, the result of any node of the graph, or an outer
/// value. The node order of a graph carries no meaning, so a node can read a
/// node that the text lists after it.
fn graph(
    program: Program<'_>,
    current: DiGraph,
    visible: &mut HashSet<SSAValue>,
    report: &mut Report,
) {
    let local = program.graph_definitions(current);
    visible.extend(local.iter().copied());
    let reads = program
        .nodes(current)
        .into_iter()
        .flat_map(|node| program.operands(node));
    for operand in reads.chain(program.graph_yields(current)) {
        if !visible.contains(&operand) {
            let value = program.named(operand);
            report.add(Violation::OutOfScope { value });
        }
    }
    for value in local {
        visible.remove(&value);
    }
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
        for child in program.graphs(statement) {
            graph(program, child, visible, report);
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
