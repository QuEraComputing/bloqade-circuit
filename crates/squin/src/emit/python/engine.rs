//! Hold the state of the Python emitter and walk the bodies of a function.

use std::convert::Infallible;

use kirin::prelude::*;
use kirin_interpreter::dialect::{Interp, Interpretable};
use kirin_interpreter::{EnvIndex, EnvStore};

use super::names::Names;
use super::{EmitPython, Py, PythonError};
use crate::ir::{Squin, query};

/// Define integer division and remainder that round toward zero, as Kirin's `div` and `rem` do.
///
/// Python's `//` and `%` round toward negative infinity, so `-7 // 2` is -4
/// where Kirin gives -3.
const TRUNCATING: &str = "def trunc_div(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def trunc_rem(a, b):
    return a - b * trunc_div(a, b)


";

/// Run the `EmitPython` rules over one function and collect its lines.
///
/// Kirin's `EnvStore` maps each SSA value to the Python expression that
/// stands for it.
pub struct PythonEmitter<'a> {
    pub(super) program: &'a StageInfo<Squin>,
    stage: CompileStage,
    pub(super) env: EnvStore<Infallible, SSAValue, Py>,
    pub(super) index: EnvIndex,
    current: Option<Statement>,
    pub(super) names: Names,
    lines: Vec<String>,
    indent: usize,
    /// Record whether a line uses `math.tau`, so the header imports `math`.
    pub(super) uses_math: bool,
    /// Record whether a line calls `trunc_div` or `trunc_rem`, so the module defines them.
    pub(super) uses_trunc: bool,
}

impl<'a> PythonEmitter<'a> {
    pub(super) fn new(program: &'a StageInfo<Squin>, stage: CompileStage) -> Self {
        let mut env = EnvStore::new();
        let index = env.alloc();
        Self {
            program,
            stage,
            env,
            index,
            current: None,
            names: Names::default(),
            lines: Vec::new(),
            indent: 0,
            uses_math: false,
            uses_trunc: false,
        }
    }

    /// Return the module text: the imports, the decorator and the kernel.
    pub(super) fn finish(self, function: &str, parameters: &[String]) -> String {
        let mut text = String::new();
        if self.uses_math {
            text.push_str("import math\n\n");
        }
        text.push_str("from bloqade import squin\n\n\n");
        if self.uses_trunc {
            text.push_str(TRUNCATING);
        }
        text.push_str("@squin.kernel\n");
        text.push_str(&format!("def {function}({}):\n", parameters.join(", ")));
        for line in &self.lines {
            text.push_str(line);
            text.push('\n');
        }
        text
    }

    /// Give each argument of the entry block a Python name, and return the names.
    pub(super) fn parameters(&mut self, entry: Block) -> Result<Vec<String>, PythonError> {
        let arguments: Vec<SSAValue> = entry
            .expect_info(self.program)
            .arguments()
            .iter()
            .map(|argument| (*argument).into())
            .collect();
        arguments
            .into_iter()
            .map(|argument| self.name(argument))
            .collect()
    }

    /// Run the rule of each statement of `block`, and then the rule of its terminator.
    pub(super) fn block(&mut self, block: Block) -> Result<(), PythonError> {
        let body: Vec<Statement> = block
            .statements(self.program)
            .chain(block.terminator(self.program))
            .collect();
        for statement in body {
            self.statement(statement)?;
        }
        Ok(())
    }

    /// Run the rule of each node of `graph` in dependency order.
    pub(super) fn graph(&mut self, graph: DiGraph) -> Result<(), PythonError> {
        let order = query::graph_order(self.program, graph)
            .ok_or_else(|| PythonError::Unsupported("a `circuit` graph with a cycle".into()))?;
        for node in order {
            self.statement(node)?;
        }
        Ok(())
    }

    /// Run the `EmitPython` rule of `statement`.
    pub(super) fn statement(&mut self, statement: Statement) -> Result<(), PythonError> {
        let outer = self.current.replace(statement);
        let definition: &'a Squin = statement.definition(self.program);
        let result = definition.interpret(self);
        self.current = outer;
        result
    }

    /// Run `walk` one indent level deeper, and write `pass` if it writes no line.
    pub(super) fn indented(
        &mut self,
        walk: impl FnOnce(&mut Self) -> Result<(), PythonError>,
    ) -> Result<(), PythonError> {
        let before = self.lines.len();
        self.indent += 1;
        let result = walk(self);
        if self.lines.len() == before {
            self.line("pass");
        }
        self.indent -= 1;
        result
    }

    /// Append one line at the current indent level.
    pub(super) fn line(&mut self, line: impl AsRef<str>) {
        let pad = "    ".repeat(self.indent);
        self.lines.push(format!("{pad}{}", line.as_ref()));
    }

    pub(super) fn line_count(&self) -> usize {
        self.lines.len()
    }

    /// Insert `line` at position `at`, one indent level deeper than the current level.
    pub(super) fn insert_line(&mut self, at: usize, line: &str) {
        let pad = "    ".repeat(self.indent + 1);
        self.lines.insert(at, format!("{pad}{line}"));
    }

    /// Check whether the lines from `start` up to `end` are one header and `pass`.
    pub(super) fn only_pass_between(&self, start: usize, end: usize) -> bool {
        end == start + 2 && self.lines[start + 1].trim() == "pass"
    }

    pub(super) fn remove_line(&mut self, at: usize) {
        self.lines.remove(at);
    }

    /// Drop every line after the first `count` lines.
    pub(super) fn truncate(&mut self, count: usize) {
        self.lines.truncate(count);
    }
}

impl Interp for PythonEmitter<'_> {
    type Value = Py;
    type Error = PythonError;
    type Effect = ();
    type Semantics = EmitPython;

    fn stage(&self) -> CompileStage {
        self.stage
    }

    fn statement(&self) -> Statement {
        self.current
            .expect("the emitter sets the statement before it runs a rule")
    }

    fn index(&self) -> EnvIndex {
        self.index
    }
}
