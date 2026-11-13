//! Answer questions about the functions, the blocks and the graphs of a stage.

use std::collections::HashSet;

use kirin::prelude::*;

use super::Squin;

/// Return the definition statement of every function specialization of `stage`.
pub fn functions(stage: &StageInfo<Squin>) -> Vec<Statement> {
    let functions = stage.staged_function_arena().iter();
    functions
        .flat_map(|function| function.specializations())
        .map(|specialization| *specialization.definition())
        .collect()
}

/// Return the blocks of the bodies of `function`, with each entry block first.
pub fn body_blocks(stage: &StageInfo<Squin>, function: Statement) -> Vec<Block> {
    let bodies = function.cfgs(stage);
    bodies.flat_map(|body| body.blocks(stage)).collect()
}

/// Return `root` and every block below it, each parent before its children.
pub fn nested_blocks(stage: &StageInfo<Squin>, root: Block) -> Vec<Block> {
    let mut blocks = vec![root];
    let mut next = 0;
    while let Some(&block) = blocks.get(next) {
        let body = block.statements(stage).chain(block.terminator(stage));
        for statement in body {
            blocks.extend(statement.blocks(stage).copied());
        }
        next += 1;
    }
    blocks
}

/// Return every block of every function of `stage`, each parent before its children.
pub fn all_blocks(stage: &StageInfo<Squin>) -> Vec<Block> {
    let functions = functions(stage);
    let roots = functions
        .iter()
        .flat_map(|function| body_blocks(stage, *function));
    roots.flat_map(|root| nested_blocks(stage, root)).collect()
}

/// Return the dataflow graphs that the statements of `blocks` own, in block order.
pub fn graphs(stage: &StageInfo<Squin>, blocks: &[Block]) -> Vec<DiGraph> {
    let statements = blocks.iter().flat_map(|block| block.statements(stage));
    statements
        .flat_map(|statement| statement.definition(stage).digraphs().copied())
        .collect()
}

/// Return every dataflow graph of every function of `stage`.
pub fn all_graphs(stage: &StageInfo<Squin>) -> Vec<DiGraph> {
    graphs(stage, &all_blocks(stage))
}

/// Return the nodes of `graph` with each node after the nodes whose results it reads.
///
/// Kirin keeps the nodes in statement order, and a rewrite can add a node
/// after the nodes that read it. Ties keep the statement order.
pub fn graph_order(stage: &StageInfo<Squin>, graph: DiGraph) -> Vec<Statement> {
    let nodes: Vec<Statement> = graph.expect_info(stage).nodes().collect();
    let inside =
        |statement: Statement| *statement.parent(stage) == Some(StatementParent::DiGraph(graph));
    let mut placed = HashSet::new();
    let mut order = Vec::with_capacity(nodes.len());
    while order.len() < nodes.len() {
        let before = order.len();
        for &node in &nodes {
            let ready =
                node.arguments(stage)
                    .all(|operand| match *operand.expect_info(stage).kind() {
                        SSAKind::Result(producer, _) => {
                            !inside(producer) || placed.contains(&producer)
                        }
                        _ => true,
                    });
            if ready && placed.insert(node) {
                order.push(node);
            }
        }
        // If a cycle leaves no node ready, the rest keep their statement order.
        if order.len() == before {
            order.extend(nodes.iter().filter(|node| !placed.contains(*node)));
            break;
        }
    }
    order
}

/// Return the name of `value` in the program text, such as `%a1`.
pub fn name(stage: &StageInfo<Squin>, value: SSAValue) -> String {
    let symbol = value.expect_info(stage).name();
    match symbol.and_then(|symbol| stage.symbol_table().resolve(symbol)) {
        Some(name) => format!("%{name}"),
        None => value.to_string(),
    }
}
