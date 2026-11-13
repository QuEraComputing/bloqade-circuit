//! Hold the state of the Stim emitter and walk the bodies of a function.

use std::convert::Infallible;

use kirin::prelude::*;
use kirin_interpreter::dialect::{Interp, Interpretable};
use kirin_interpreter::{EnvIndex, EnvStore};

use super::{EmitStim, StimError};
use crate::analysis::address::Addresses;
use crate::emit::qubits::Qubits;
use crate::ir::{Squin, query};

/// Run the `EmitStim` rules over one function and collect its instructions.
///
/// A Stim circuit has no classical values, so the engine keeps no SSA facts.
/// It holds one empty Kirin environment, because `Interp` names the current
/// activation.
pub struct StimEmitter<'a> {
    pub(super) program: &'a StageInfo<Squin>,
    pub(super) addresses: &'a Addresses<'a>,
    stage: CompileStage,
    index: EnvIndex,
    current: Option<Statement>,
    lines: Vec<String>,
    qubits: Qubits<'a>,
}

impl<'a> StimEmitter<'a> {
    pub(super) fn new(
        program: &'a StageInfo<Squin>,
        stage: CompileStage,
        addresses: &'a Addresses<'a>,
    ) -> Self {
        let index = EnvStore::<Infallible, SSAValue, ()>::new().alloc();
        Self {
            program,
            addresses,
            stage,
            index,
            current: None,
            lines: Vec::new(),
            qubits: Qubits::new(program, addresses),
        }
    }

    pub(super) fn finish(self) -> String {
        self.lines.iter().map(|line| format!("{line}\n")).collect()
    }

    /// Run the rule of each statement of `block`, and then the rule of its terminator.
    pub(super) fn block(&mut self, block: Block) -> Result<(), StimError> {
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
    ///
    /// Any topological order gives the same circuit, because each gate
    /// follows the gates whose wires it reads.
    pub(super) fn graph(&mut self, graph: DiGraph) -> Result<(), StimError> {
        let order = query::graph_order(self.program, graph)
            .ok_or_else(|| StimError::Unsupported("a `circuit` graph with a cycle".into()))?;
        for node in order {
            self.statement(node)?;
        }
        Ok(())
    }

    /// Run the `EmitStim` rule of `statement`.
    pub(super) fn statement(&mut self, statement: Statement) -> Result<(), StimError> {
        let outer = self.current.replace(statement);
        let definition: &'a Squin = statement.definition(self.program);
        let result = definition.interpret(self);
        self.current = outer;
        result
    }

    /// Give a Stim index to each qubit of `value`, and reset a reused index.
    pub(super) fn allocate(&mut self, value: SSAValue) -> Result<(), StimError> {
        for (index, reused) in self.qubits.allocate(value)? {
            if reused {
                self.instruction("R", &[index]);
            }
        }
        Ok(())
    }

    pub(super) fn release(&mut self, value: SSAValue) -> Result<(), StimError> {
        Ok(self.qubits.release(value)?)
    }

    pub(super) fn indices_of(&self, value: SSAValue) -> Result<Vec<u32>, StimError> {
        Ok(self.qubits.indices_of(value)?)
    }

    pub(super) fn index(&self, wire: SSAValue) -> Result<u32, StimError> {
        Ok(self.qubits.index(wire)?)
    }

    /// Append the instruction `name` on the Stim targets `qubits`.
    pub(super) fn instruction(&mut self, name: &str, qubits: &[u32]) {
        let targets: Vec<String> = qubits.iter().map(u32::to_string).collect();
        self.lines.push(format!("{name} {}", targets.join(" ")));
    }
}

impl Interp for StimEmitter<'_> {
    type Value = ();
    type Error = StimError;
    type Effect = ();
    type Semantics = EmitStim;

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
