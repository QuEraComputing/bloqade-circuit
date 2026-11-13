//! Lower circuit regions, branches and loops to ppvm labels and branches.

use kirin::prelude::*;
use kirin_scf::StructuredControlFlow;

use super::PpvmError;
use super::locals::Slot;
use super::writer::Writer;
use crate::ir::{Squin, query};

impl Writer<'_> {
    /// Write a statement that owns a region, a branch or a loop, or a classical statement.
    pub(super) fn control(&mut self, statement: Statement) -> Result<(), PpvmError> {
        match statement.definition(self.program) {
            Squin::Circuit(region) => {
                let body = region.body;
                let ports = body.expect_info(self.program).ports().to_vec();
                for (port, input) in ports.into_iter().zip(region.inputs.clone()) {
                    self.locals.alias(port.into(), input);
                }
                let order = query::graph_order(self.program, body).ok_or_else(|| {
                    PpvmError::Unsupported("a `circuit` graph with a cycle".into())
                })?;
                for node in order {
                    self.statement(node)?;
                }
                let yields = body.expect_info(self.program).yields().to_vec();
                for (result, value) in region.results.clone().into_iter().zip(yields) {
                    self.locals.alias(result.into(), value);
                }
            }
            Squin::Conditional(branch) => {
                let (condition, inputs) = (branch.condition, branch.inputs.clone());
                let arms = [branch.then_body, branch.else_body];
                let results: Vec<SSAValue> = branch.results.iter().map(|r| (*r).into()).collect();
                self.branch(condition, arms, &inputs, &results)?;
            }
            Squin::Structured(StructuredControlFlow::If(branch)) => {
                let arms = [branch.then_block(), branch.else_block()];
                let results: Vec<SSAValue> = branch.results().iter().map(|r| (*r).into()).collect();
                self.branch(branch.condition(), arms, &[], &results)?;
            }
            Squin::Repeat(repeat) => {
                let (body, inputs) = (repeat.body, repeat.inputs.clone());
                let results: Vec<SSAValue> = repeat.results.iter().map(|r| (*r).into()).collect();
                self.repeat(body, &inputs, &results)?;
            }
            Squin::Structured(StructuredControlFlow::For(lp)) => {
                let bounds = [lp.start(), lp.end(), lp.step()];
                let (body, inputs) = (lp.body(), lp.init_args().to_vec());
                let results: Vec<SSAValue> = lp.results().iter().map(|r| (*r).into()).collect();
                self.counted(bounds, body, &inputs, &results)?;
            }
            Squin::Structured(StructuredControlFlow::Yield(_)) => {}
            _ => self.classical(statement)?,
        }
        Ok(())
    }

    /// Run the arm that `condition` selects, and store its yields in the slots of `results`.
    ///
    /// Arm argument `k` shares the slots of `inputs[k]`, because no statement
    /// of the arm can change an input.
    fn branch(
        &mut self,
        condition: SSAValue,
        arms: [Block; 2],
        inputs: &[SSAValue],
        results: &[SSAValue],
    ) -> Result<(), PpvmError> {
        let targets: Vec<Vec<Slot>> = results.iter().map(|result| self.define(*result)).collect();
        let labels = [self.label(), self.label()];
        let join = self.label();
        self.load(condition)?;
        self.line(format!("cpu::cpu.cond_br {}, {}", labels[0], labels[1]));
        for (arm, label) in arms.into_iter().zip(labels) {
            self.line(format!("cpu::cpu.label {label}"));
            for (argument, input) in self.arguments(arm).into_iter().zip(inputs) {
                self.locals.alias(argument, *input);
            }
            self.block(arm)?;
            let yields = self.yields(arm);
            self.copy(&yields, &targets)?;
            self.line(format!("cpu::cpu.br {join}"));
        }
        self.line(format!("cpu::cpu.label {join}"));
        Ok(())
    }

    /// Rerun `body` until its stop flag is true, as a `repeat` does.
    ///
    /// The body arguments get their own slots, because each run overwrites
    /// them with the values that the previous run yields.
    fn repeat(
        &mut self,
        body: Block,
        inputs: &[SSAValue],
        results: &[SSAValue],
    ) -> Result<(), PpvmError> {
        let arguments = self.arguments(body);
        let carried = self.carried(&arguments, inputs)?;
        let (start, done) = (self.label(), self.label());
        self.line(format!("cpu::cpu.label {start}"));
        self.in_loop(|writer| writer.block(body))?;
        let yields = self.yields(body);
        let (stop, values) = yields
            .split_first()
            .ok_or_else(|| PpvmError::Unsupported("a `repeat` body without a stop flag".into()))?;
        self.copy(values, &carried)?;
        self.load(*stop)?;
        self.line(format!("cpu::cpu.cond_br {done}, {start}"));
        self.line(format!("cpu::cpu.label {done}"));
        for (result, slots) in results.iter().zip(carried) {
            self.locals.set(*result, slots);
        }
        Ok(())
    }

    /// Run `body` for each index from `start` up to `end`, as a Kirin `for` does.
    fn counted(
        &mut self,
        [start, end, step]: [SSAValue; 3],
        body: Block,
        inputs: &[SSAValue],
        results: &[SSAValue],
    ) -> Result<(), PpvmError> {
        let arguments = self.arguments(body);
        let (index, rest) = arguments
            .split_first()
            .ok_or_else(|| PpvmError::Unsupported("a `for` body without an index".into()))?;
        let index_slots = self.carried(&[*index], &[start])?;
        let carried = self.carried(rest, inputs)?;
        let (head, run, done) = (self.label(), self.label(), self.label());
        self.line(format!("cpu::cpu.label {head}"));
        self.load(*index)?;
        self.load(end)?;
        self.line("cpu::cpu.lt i64".to_string());
        self.line(format!("cpu::cpu.cond_br {run}, {done}"));
        self.line(format!("cpu::cpu.label {run}"));
        self.in_loop(|writer| writer.block(body))?;
        let yields = self.yields(body);
        self.copy(&yields, &carried)?;
        self.load(*index)?;
        self.load(step)?;
        self.line("cpu::cpu.add i64".to_string());
        self.copy_top(&index_slots[0]);
        self.line(format!("cpu::cpu.br {head}"));
        self.line(format!("cpu::cpu.label {done}"));
        for (result, slots) in results.iter().zip(carried) {
            self.locals.set(*result, slots);
        }
        Ok(())
    }

    /// Give each of `arguments` new slots and copy the value at its position in `inputs` there.
    fn carried(
        &mut self,
        arguments: &[SSAValue],
        inputs: &[SSAValue],
    ) -> Result<Vec<Vec<Slot>>, PpvmError> {
        let slots: Vec<Vec<Slot>> = arguments
            .iter()
            .map(|argument| self.define(*argument))
            .collect();
        self.copy(inputs, &slots)?;
        Ok(slots)
    }

    /// Pop the top of the stack into `slots`.
    fn copy_top(&mut self, slots: &[Slot]) {
        for (slot, kind) in slots.iter().rev() {
            self.line(format!("cpu::cpu.store {kind}, {slot}"));
        }
    }

    fn arguments(&self, block: Block) -> Vec<SSAValue> {
        let arguments = block.expect_info(self.program).arguments();
        arguments
            .iter()
            .map(|argument| (*argument).into())
            .collect()
    }

    fn yields(&self, block: Block) -> Vec<SSAValue> {
        match block.terminator(self.program) {
            Some(terminator) => terminator.arguments(self.program).copied().collect(),
            None => Vec::new(),
        }
    }
}
