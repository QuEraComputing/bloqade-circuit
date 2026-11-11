use kirin::prelude::*;

use super::violation::Named;
use crate::language::Squin;
use crate::types::SquinType;

/// Answer the questions that the verifier rules ask about one stage.
#[derive(Clone, Copy)]
pub(super) struct Program<'a> {
    stage: &'a StageInfo<Squin>,
}

impl<'a> Program<'a> {
    pub(super) fn new(stage: &'a StageInfo<Squin>) -> Self {
        Self { stage }
    }

    /// Return the type of `value`.
    pub(super) fn ty(self, value: impl Into<SSAValue>) -> SquinType {
        *value.into().expect_info(self.stage).ty()
    }

    /// Return `value` with its text name, such as `%r1`.
    pub(super) fn named(self, value: impl Into<SSAValue>) -> Named {
        let value = value.into();
        let symbol = value.expect_info(self.stage).name();
        let name = match symbol.and_then(|symbol| self.stage.symbol_table().resolve(symbol)) {
            Some(name) => format!("%{name}"),
            None => value.to_string(),
        };
        Named { value, name }
    }

    /// Return the statement that produces `value` and the index of that result.
    pub(super) fn producer(self, value: SSAValue) -> Option<(Statement, usize)> {
        match *value.expect_info(self.stage).kind() {
            SSAKind::Result(statement, index) => Some((statement, index)),
            _ => None,
        }
    }

    /// Return the block that defines `value` as an argument or as a result.
    pub(super) fn home(self, value: SSAValue) -> Option<Block> {
        match *value.expect_info(self.stage).kind() {
            SSAKind::Result(statement, _) => self.parent(statement),
            SSAKind::BlockArgument(block, _) => Some(block),
            SSAKind::Port(..) => None,
        }
    }

    /// Return the block that holds `statement`.
    pub(super) fn parent(self, statement: Statement) -> Option<Block> {
        match *statement.parent(self.stage) {
            Some(StatementParent::Block(block)) => Some(block),
            _ => None,
        }
    }

    /// Return the positions that read `value`.
    pub(super) fn uses(self, value: SSAValue) -> &'a [Use] {
        value.expect_info(self.stage).uses()
    }

    pub(super) fn definition(self, statement: Statement) -> &'a Squin {
        statement.definition(self.stage)
    }

    pub(super) fn operands(self, statement: Statement) -> impl Iterator<Item = SSAValue> + 'a {
        statement.arguments(self.stage).copied()
    }

    pub(super) fn results(self, statement: Statement) -> impl Iterator<Item = SSAValue> + 'a {
        statement.results(self.stage).map(|result| (*result).into())
    }

    pub(super) fn arguments(self, block: Block) -> impl Iterator<Item = SSAValue> + 'a {
        let arguments = block.expect_info(self.stage).arguments();
        arguments.iter().map(|argument| (*argument).into())
    }

    /// Return the statements of `block` in order, with the terminator last.
    pub(super) fn body(self, block: Block) -> impl Iterator<Item = Statement> + 'a {
        block
            .statements(self.stage)
            .chain(block.terminator(self.stage))
    }

    /// Return the values that the terminator of `block` passes on.
    pub(super) fn yields(self, block: Block) -> Vec<SSAValue> {
        match block.terminator(self.stage) {
            Some(terminator) => self.operands(terminator).collect(),
            None => Vec::new(),
        }
    }

    /// Return the values that `block` defines: its arguments and then its results.
    pub(super) fn definitions(self, block: Block) -> impl Iterator<Item = SSAValue> + 'a {
        let results = self
            .body(block)
            .flat_map(move |statement| self.results(statement));
        self.arguments(block).chain(results)
    }

    /// Return the body block of every function of the stage.
    pub(super) fn roots(self) -> Vec<Block> {
        let functions = self.stage.staged_function_arena().iter();
        functions
            .flat_map(|function| function.specializations())
            .flat_map(|specialization| specialization.definition().cfgs(self.stage))
            .flat_map(|cfg| cfg.blocks(self.stage))
            .collect()
    }

    /// Return `root` and every block below it, each parent before its children.
    pub(super) fn blocks(self, root: Block) -> Vec<Block> {
        let mut blocks = vec![root];
        let mut next = 0;
        while let Some(&block) = blocks.get(next) {
            for statement in self.body(block) {
                blocks.extend(statement.blocks(self.stage).copied());
            }
            next += 1;
        }
        blocks
    }
}
