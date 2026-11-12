//! Answer questions about the functions and the blocks of a stage.

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

/// Return the name of `value` in the program text, such as `%a1`.
pub fn name(stage: &StageInfo<Squin>, value: SSAValue) -> String {
    let symbol = value.expect_info(stage).name();
    match symbol.and_then(|symbol| stage.symbol_table().resolve(symbol)) {
        Some(name) => format!("%{name}"),
        None => value.to_string(),
    }
}
