//! Check that gates sit in `circuit` graphs and control flow sits in blocks.

use kirin::prelude::*;

use super::program::Program;
use super::structure::{Place, Structure};
use super::violation::{Report, Violation};

/// Check each statement of `blocks` and each node of `graphs`.
pub(super) fn check(
    program: Program<'_>,
    blocks: &[Block],
    graphs: &[DiGraph],
    report: &mut Report,
) {
    for block in blocks {
        for statement in program.body(*block) {
            if program.definition(statement).place() == Place::Graph {
                let site = program.describe(statement);
                let expected = "the graph of a `circuit`";
                report.add(Violation::Misplaced { site, expected });
            }
        }
    }
    for graph in graphs {
        for node in program.nodes(*graph) {
            if program.definition(node).place() == Place::Block {
                let site = program.describe(node);
                report.add(Violation::Misplaced {
                    site,
                    expected: "a block",
                });
            }
        }
    }
}
