//! Hold the state of the ppvm emitter and walk the bodies of a function.

use std::collections::HashMap;
use std::convert::Infallible;

use kirin::prelude::*;
use kirin_interpreter::dialect::{Interp, Interpretable};
use kirin_interpreter::{Env, EnvIndex, EnvStore};

use super::locals::Slot;
use super::source::one_line;
use super::{EmitPpvm, PpvmError};
use crate::analysis::address::Addresses;
use crate::emit::qubits::Qubits;
use crate::ir::{Squin, query};

/// Name the column where the comment behind an instruction starts.
const COMMENT_COLUMN: usize = 32;

/// Run the `EmitPpvm` rules over one function and collect its instructions.
///
/// Kirin's `EnvStore` maps each classical SSA value to its CPU slots. The
/// qubit pool maps each wire to the qubit index that the address analysis
/// fixes.
pub struct PpvmEmitter<'a> {
    pub(super) program: &'a StageInfo<Squin>,
    pub(super) addresses: &'a Addresses<'a>,
    pub(super) qubits: Qubits<'a>,
    stage: CompileStage,
    pub(super) env: EnvStore<Infallible, SSAValue, Vec<Slot>>,
    pub(super) index: EnvIndex,
    current: Option<Statement>,
    /// Hold the lines that run before the body, such as the register tables.
    pub(super) prologue: Vec<String>,
    /// Map the qubit indices of a register to the slot of its table.
    pub(super) tables: HashMap<Vec<u32>, Slot>,
    lines: Vec<String>,
    pub(super) slots: u32,
    labels: u32,
    /// Count the loops around the current statement.
    pub(super) loops: u32,
}

impl<'a> PpvmEmitter<'a> {
    pub(super) fn new(
        program: &'a StageInfo<Squin>,
        stage: CompileStage,
        addresses: &'a Addresses<'a>,
    ) -> Self {
        let mut env = EnvStore::new();
        let index = env.alloc();
        Self {
            program,
            addresses,
            qubits: Qubits::new(program, addresses),
            stage,
            env,
            index,
            current: None,
            prologue: Vec::new(),
            tables: HashMap::new(),
            lines: Vec::new(),
            slots: 0,
            labels: 0,
            loops: 0,
        }
    }

    /// Return the `.sst` text: the device header, then `@main` with its slots reserved.
    ///
    /// ppvm keeps locals on the operand stack, and its `.sst` reader sets the
    /// local count to 0. So `@main` first pushes one placeholder per slot. The
    /// prologue follows, and then the body.
    pub(super) fn finish(self) -> String {
        let mut text = format!(
            "device circuit.n_qubits {};\n\nfn @main() {{\n",
            self.qubits.count()
        );
        for _ in 0..self.slots {
            text.push_str("    cpu::cpu.const bool, false\n");
        }
        for line in self.prologue.iter().chain(&self.lines) {
            text.push_str(&format!("    {line}\n"));
        }
        text.push_str("}\n");
        text
    }

    /// Run the rule of each statement of `block`, and then the rule of its terminator.
    ///
    /// A `ret` ends the function. A `yield` writes nothing, because the rule
    /// that owns the block copies the yielded values.
    pub(super) fn block(&mut self, block: Block) -> Result<(), PpvmError> {
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
    pub(super) fn graph(&mut self, graph: DiGraph) -> Result<(), PpvmError> {
        let order = query::graph_order(self.program, graph)
            .ok_or_else(|| PpvmError::Unsupported("a `circuit` graph with a cycle".into()))?;
        for node in order {
            self.statement(node)?;
        }
        Ok(())
    }

    /// Run the `EmitPpvm` rule of `statement`, and mark its first instruction with the statement.
    ///
    /// The first line that the rule writes gets ` // ` and the statement on
    /// one line. A statement that writes no instruction gets no comment. If a
    /// nested statement already marked that line, the outer statement leaves
    /// it, so each comment names the statement closest to its instruction.
    pub(super) fn statement(&mut self, statement: Statement) -> Result<(), PpvmError> {
        let first = self.lines.len();
        let outer = self.current.replace(statement);
        let definition: &'a Squin = statement.definition(self.program);
        let result = definition.interpret(self);
        self.current = outer;
        if let Some(line) = self.lines.get_mut(first)
            && !line.contains("//")
        {
            let source = one_line(self.program, statement);
            *line = format!("{line:<COMMENT_COLUMN$} // {source}");
        }
        result
    }

    /// Append one instruction line.
    pub(super) fn line(&mut self, line: String) {
        self.lines.push(line);
    }

    /// Return a new label, such as `@l3`.
    pub(super) fn label(&mut self) -> String {
        self.labels += 1;
        format!("@l{}", self.labels - 1)
    }
}

impl Interp for PpvmEmitter<'_> {
    type Value = Vec<Slot>;
    type Error = PpvmError;
    type Effect = ();
    type Semantics = EmitPpvm;

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

impl Env for PpvmEmitter<'_> {
    type Anchor = SSAValue;

    /// Return the slots of `anchor`, or an error if no rule defined it yet.
    fn env_read(&self, index: EnvIndex, anchor: SSAValue) -> Result<Vec<Slot>, PpvmError> {
        self.env.read(index, anchor)?.ok_or_else(|| {
            let name = query::name(self.program, anchor);
            PpvmError::Unsupported(format!("the value {name} before its definition"))
        })
    }

    fn env_write(
        &mut self,
        index: EnvIndex,
        anchor: SSAValue,
        data: Vec<Slot>,
    ) -> Result<(), PpvmError> {
        Ok(self.env.write(index, anchor, data)?)
    }
}
