//! Print a squin statement on one line for the comment behind its instructions.

use kirin::prelude::*;

use crate::ir::Squin;

/// Print a statement on one line, with each nested body shown as `{...}`.
struct OneLine(Statement);

impl PrettyPrint for OneLine {
    fn namespaced_pretty_print<'a, L: Dialect + PrettyPrint>(
        &self,
        doc: &'a Document<'a, L>,
        _namespace: &[&str],
    ) -> ArenaDoc<'a>
    where
        L::Type: std::fmt::Display,
    {
        doc.print_statement_abbreviated(&self.0)
    }
}

/// Return `statement` as one line of squin text, such as `%a1 = h %a0`.
pub(super) fn one_line(program: &StageInfo<Squin>, statement: Statement) -> String {
    let text = OneLine(statement).sprint(program);
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}
