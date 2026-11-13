//! Write the labels and branches of a branch statement or a loop around its bodies.
//!
//! Each helper walks every body once. A loop body therefore appears once in
//! the program, and a branch back to its label runs it again.

use kirin::prelude::*;

use super::PpvmEmitter;
use super::PpvmError;
use super::locals::Slot;

impl PpvmEmitter<'_> {
    /// Run the arm that `condition` selects, and store its yields in the slots of `results`.
    ///
    /// Arm argument `k` shares the slots of `inputs[k]`, because no statement
    /// of the arm can change an input. A wire result whose qubit the analysis
    /// does not know gets a `u64` slot, and each arm stores the qubit index of
    /// its yield there.
    pub(super) fn branch(
        &mut self,
        condition: SSAValue,
        arms: [Block; 2],
        inputs: &[SSAValue],
        results: &[SSAValue],
    ) -> Result<(), PpvmError> {
        let targets = self.define_all_carried(results)?;
        let labels = [self.label(), self.label()];
        let join = self.label();
        self.load(condition)?;
        self.line(format!("cpu::cpu.cond_br {}, {}", labels[0], labels[1]));
        for (arm, label) in arms.into_iter().zip(labels) {
            self.line(format!("cpu::cpu.label {label}"));
            for (argument, input) in self.arguments(arm).into_iter().zip(inputs) {
                self.alias(argument, *input)?;
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
    pub(super) fn repeat_loop(
        &mut self,
        body: Block,
        inputs: &[SSAValue],
        results: &[SSAValue],
    ) -> Result<(), PpvmError> {
        let arguments = self.arguments(body);
        let carried = self.carried(&arguments, inputs)?;
        let (start, done) = (self.label(), self.label());
        self.line(format!("cpu::cpu.label {start}"));
        self.in_loop(|emitter| emitter.block(body))?;
        let yields = self.yields(body);
        let (stop, values) = yields
            .split_first()
            .ok_or_else(|| PpvmError::Unsupported("a `repeat` body without a stop flag".into()))?;
        self.copy(values, &carried)?;
        self.load(*stop)?;
        self.line(format!("cpu::cpu.cond_br {done}, {start}"));
        self.line(format!("cpu::cpu.label {done}"));
        self.set_all(results, carried)
    }

    /// Run `body` for each index from `start` up to `end`, as a Kirin `for` does.
    pub(super) fn counted(
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
        self.in_loop(|emitter| emitter.block(body))?;
        let yields = self.yields(body);
        self.copy(&yields, &carried)?;
        self.load(*index)?;
        self.load(step)?;
        self.line("cpu::cpu.add i64".to_string());
        self.store_into(&index_slots[0]);
        self.line(format!("cpu::cpu.br {head}"));
        self.line(format!("cpu::cpu.label {done}"));
        self.set_all(results, carried)
    }

    /// Give each of `arguments` new slots and copy the value at its position in `inputs` there.
    ///
    /// A wire argument whose qubit the analysis does not know gets a `u64`
    /// slot, so the loop carries its qubit index like a classical value.
    fn carried(
        &mut self,
        arguments: &[SSAValue],
        inputs: &[SSAValue],
    ) -> Result<Vec<Vec<Slot>>, PpvmError> {
        let slots = self.define_all_carried(arguments)?;
        self.copy(inputs, &slots)?;
        Ok(slots)
    }

    fn define_all_carried(&mut self, values: &[SSAValue]) -> Result<Vec<Vec<Slot>>, PpvmError> {
        values
            .iter()
            .map(|value| self.define_carried(*value))
            .collect()
    }

    /// Let each of `results` use the slots at its position in `slots`.
    fn set_all(&mut self, results: &[SSAValue], slots: Vec<Vec<Slot>>) -> Result<(), PpvmError> {
        for (result, slots) in results.iter().zip(slots) {
            if !slots.is_empty() {
                self.set(*result, slots)?;
            }
        }
        Ok(())
    }

    /// Run `walk` with the loop count raised by one.
    fn in_loop(
        &mut self,
        walk: impl FnOnce(&mut Self) -> Result<(), PpvmError>,
    ) -> Result<(), PpvmError> {
        self.loops += 1;
        let result = walk(self);
        self.loops -= 1;
        result
    }

    fn arguments(&self, block: Block) -> Vec<SSAValue> {
        let arguments = block.expect_info(self.program).arguments();
        arguments
            .iter()
            .map(|argument| (*argument).into())
            .collect()
    }

    /// Return the values that the terminator of `block` yields.
    pub(super) fn yields(&self, block: Block) -> Vec<SSAValue> {
        match block.terminator(self.program) {
            Some(terminator) => terminator.arguments(self.program).copied().collect(),
            None => Vec::new(),
        }
    }
}
