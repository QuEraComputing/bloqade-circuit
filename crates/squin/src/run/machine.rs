use std::collections::HashMap;

use kirin::prelude::*;
use kirin_scf::{For, If, StructuredControlFlow};

use super::{Backend, Failure, Operation, Qubit, Value};
use crate::bits::BitsOp;
use crate::gate::Gate;
use crate::language::Squin;
use crate::state::State;
use crate::types::SquinType;

type Run<T> = Result<T, Failure>;

/// Evaluate the statements of one stage against a backend.
///
/// The machine keeps one value for each SSA value. It removes the value of a
/// wire, a register or a slot when a statement reads it, because that
/// statement consumes it.
pub struct Machine<'a, B: Backend> {
    stage: &'a StageInfo<Squin>,
    backend: &'a mut B,
    values: HashMap<SSAValue, Value<B::Bit>>,
}

impl<'a, B: Backend> Machine<'a, B> {
    pub fn new(stage: &'a StageInfo<Squin>, backend: &'a mut B) -> Self {
        let values = HashMap::new();
        Self {
            stage,
            backend,
            values,
        }
    }

    /// Run `block` with `arguments` and return the values that its terminator passes on.
    pub fn block(
        &mut self,
        block: Block,
        arguments: Vec<Value<B::Bit>>,
    ) -> Run<Vec<Value<B::Bit>>> {
        let parameters = block.expect_info(self.stage).arguments();
        if parameters.len() != arguments.len() {
            let (expected, found) = (parameters.len(), arguments.len());
            return Err(Failure::Arity { expected, found });
        }
        for (parameter, argument) in parameters.iter().zip(arguments) {
            self.values.insert((*parameter).into(), argument);
        }
        for statement in block.statements(self.stage) {
            self.statement(statement)?;
        }
        let terminator = block.terminator(self.stage);
        let passed = terminator
            .into_iter()
            .flat_map(|last| last.arguments(self.stage));
        passed.map(|value| self.read(*value)).collect()
    }

    fn statement(&mut self, statement: Statement) -> Run<()> {
        match statement.definition(self.stage) {
            Squin::Constant(constant) => self.write(constant.result, Value::Int(constant.value)),
            Squin::State(state) => self.state(state)?,
            Squin::Gate(gate) => self.gate(gate)?,
            Squin::Bits(bits) => self.bits(bits)?,
            Squin::Structured(StructuredControlFlow::If(branch)) => self.branch(branch)?,
            Squin::Structured(StructuredControlFlow::For(repeat)) => self.repeat(repeat)?,
            _ => {}
        }
        Ok(())
    }

    fn state(&mut self, state: &State) -> Run<()> {
        match *state {
            State::Alloc { wire } => {
                let qubit = self.backend.alloc()?;
                self.write(wire, Value::Wire(qubit));
            }
            State::Free { wire } => {
                let qubit = self.wire(wire)?;
                self.backend.free(qubit)?;
            }
            State::AllocRegister { size, register } => {
                let size = self.int(size)?;
                let count = usize::try_from(size).map_err(|_| Failure::Size(size))?;
                let qubits = (0..count).map(|_| self.backend.alloc().map(Some));
                let qubits = qubits.collect::<Run<_>>()?;
                self.write(register, Value::Register(qubits));
            }
            State::FreeRegister { register } => {
                for qubit in self.whole(register)? {
                    self.backend.free(qubit)?;
                }
            }
            State::Borrow {
                register,
                index,
                register_out,
                slot,
                wire,
            } => {
                let mut qubits = self.register(register)?;
                let index = position(self.int(index)?, qubits.len())?;
                let qubit = qubits[index].take().ok_or(Failure::Lent { index })?;
                self.write(register_out, Value::Register(qubits));
                self.write(slot, Value::Slot(index));
                self.write(wire, Value::Wire(qubit));
            }
            State::Release {
                register,
                slot,
                wire,
                register_out,
            } => {
                let mut qubits = self.register(register)?;
                let index = self.slot(slot)?;
                qubits[index] = Some(self.wire(wire)?);
                self.write(register_out, Value::Register(qubits));
            }
            State::Replace {
                register,
                index,
                wire,
                register_out,
                wire_out,
            } => {
                let mut qubits = self.register(register)?;
                let index = position(self.int(index)?, qubits.len())?;
                let old = qubits[index].replace(self.wire(wire)?);
                self.write(register_out, Value::Register(qubits));
                self.write(wire_out, Value::Wire(old.ok_or(Failure::Lent { index })?));
            }
            State::Pack {
                ref wires,
                register,
            } => {
                let qubits = wires.iter().map(|wire| self.wire(*wire).map(Some));
                let qubits = qubits.collect::<Run<_>>()?;
                self.write(register, Value::Register(qubits));
            }
            State::Split {
                register,
                index,
                before,
                after,
            } => {
                let mut qubits = self.register(register)?;
                let index = self.int(index)?;
                let length = qubits.len();
                let cut = usize::try_from(index).ok().filter(|cut| *cut <= length);
                let rest = qubits.split_off(cut.ok_or(Failure::Index { index, length })?);
                self.write(before, Value::Register(qubits));
                self.write(after, Value::Register(rest));
            }
            State::Join {
                first,
                second,
                register,
            } => {
                let mut qubits = self.register(first)?;
                qubits.extend(self.register(second)?);
                self.write(register, Value::Register(qubits));
            }
            State::Length {
                register,
                register_out,
                length,
            } => {
                let qubits = self.register(register)?;
                self.write(length, Value::Int(qubits.len() as i64));
                self.write(register_out, Value::Register(qubits));
            }
            State::Measure {
                wire,
                wire_out,
                bit,
            } => {
                let qubit = self.wire(wire)?;
                let mut results = self.backend.measure(&[qubit])?;
                let result = results.pop().ok_or(Failure::Arity {
                    expected: 1,
                    found: 0,
                })?;
                self.write(wire_out, Value::Wire(qubit));
                self.write(bit, Value::Bit(result));
            }
            State::MeasureRegister {
                register,
                register_out,
                bits,
            } => {
                let qubits = self.whole(register)?;
                let results = self.backend.measure(&qubits)?;
                let qubits = qubits.into_iter().map(Some).collect();
                self.write(register_out, Value::Register(qubits));
                self.write(bits, Value::Bits(results));
            }
            State::Reset { wire, wire_out } => {
                let qubit = self.wire(wire)?;
                self.backend.reset(qubit)?;
                self.write(wire_out, Value::Wire(qubit));
            }
        }
        Ok(())
    }

    fn gate(&mut self, gate: &Gate) -> Run<()> {
        let (operation, wires, outputs) = match *gate {
            Gate::Fixed {
                kind,
                wire,
                wire_out,
            } => (Operation::Fixed(kind), vec![wire], vec![wire_out]),
            Gate::Rotation {
                axis,
                angle,
                wire,
                wire_out,
            } => {
                let operation = Operation::Rotation(axis, self.float(angle)?);
                (operation, vec![wire], vec![wire_out])
            }
            Gate::U3 {
                theta,
                phi,
                lam,
                wire,
                wire_out,
            } => {
                let (theta, phi, lam) = (self.float(theta)?, self.float(phi)?, self.float(lam)?);
                (Operation::U3(theta, phi, lam), vec![wire], vec![wire_out])
            }
            Gate::Controlled {
                kind,
                control,
                target,
                control_out,
                target_out,
            } => {
                let outputs = vec![control_out, target_out];
                (Operation::Controlled(kind), vec![control, target], outputs)
            }
        };
        let qubits = wires.into_iter().map(|wire| self.wire(wire));
        let qubits = qubits.collect::<Run<Vec<_>>>()?;
        self.backend.gate(operation, &qubits)?;
        for (output, qubit) in outputs.into_iter().zip(qubits) {
            self.write(output, Value::Wire(qubit));
        }
        Ok(())
    }

    fn bits(&mut self, bits: &BitsOp) -> Run<()> {
        match *bits {
            BitsOp::Pack { ref bits, result } => {
                let results = bits.iter().map(|bit| match self.read(*bit)? {
                    Value::Bit(result) => Ok(result),
                    other => Err(wrong("a measurement result", &other)),
                });
                let results = results.collect::<Run<_>>()?;
                self.write(result, Value::Bits(results));
            }
            BitsOp::Get { bits, index, bit } => {
                let results = self.results(bits)?;
                let index = position(self.int(index)?, results.len())?;
                self.write(bit, Value::Bit(results[index].clone()));
            }
            BitsOp::Length { bits, length } => {
                let count = self.results(bits)?.len();
                self.write(length, Value::Int(count as i64));
            }
        }
        Ok(())
    }

    /// Run the arm that the condition selects and bind what the arm yields.
    fn branch(&mut self, branch: &If<SquinType>) -> Run<()> {
        let arm = match self.read(branch.condition())? {
            Value::Bool(true) => branch.then_block(),
            Value::Bool(false) => branch.else_block(),
            other => return Err(wrong("a truth value", &other)),
        };
        let yielded = self.block(arm, Vec::new())?;
        self.bind(branch.results(), yielded)
    }

    /// Run the loop body once for each index and pass the carried values along.
    fn repeat(&mut self, repeat: &For<SquinType>) -> Run<()> {
        let (start, end) = (self.int(repeat.start())?, self.int(repeat.end())?);
        let step = self.int(repeat.step())?;
        let stride = usize::try_from(step).ok().filter(|stride| *stride > 0);
        let stride = stride.ok_or(Failure::Step(step))?;
        let carried = repeat.init_args().iter().map(|value| self.read(*value));
        let mut carried = carried.collect::<Run<Vec<_>>>()?;
        for index in (start..end).step_by(stride) {
            carried.insert(0, Value::Int(index));
            carried = self.block(repeat.body(), carried)?;
        }
        self.bind(repeat.results(), carried)
    }

    fn bind(&mut self, results: &[ResultValue], values: Vec<Value<B::Bit>>) -> Run<()> {
        if results.len() != values.len() {
            let (expected, found) = (results.len(), values.len());
            return Err(Failure::Arity { expected, found });
        }
        for (result, value) in results.iter().zip(values) {
            self.write(*result, value);
        }
        Ok(())
    }

    fn write(&mut self, target: impl Into<SSAValue>, value: Value<B::Bit>) {
        self.values.insert(target.into(), value);
    }

    /// Return the value of `source`, and remove it if its type is linear.
    fn read(&mut self, source: impl Into<SSAValue>) -> Run<Value<B::Bit>> {
        let source = source.into();
        let value = if source.expect_info(self.stage).ty().is_linear() {
            self.values.remove(&source)
        } else {
            self.values.get(&source).cloned()
        };
        value.ok_or_else(|| Failure::Unbound(source.to_string()))
    }

    fn int(&mut self, source: SSAValue) -> Run<i64> {
        match self.read(source)? {
            Value::Int(value) => Ok(value),
            other => Err(wrong("an integer", &other)),
        }
    }

    fn float(&mut self, source: SSAValue) -> Run<f64> {
        match self.read(source)? {
            Value::Float(value) => Ok(value),
            other => Err(wrong("a float", &other)),
        }
    }

    fn wire(&mut self, source: SSAValue) -> Run<Qubit> {
        match self.read(source)? {
            Value::Wire(qubit) => Ok(qubit),
            other => Err(wrong("a wire", &other)),
        }
    }

    fn slot(&mut self, source: SSAValue) -> Run<usize> {
        match self.read(source)? {
            Value::Slot(index) => Ok(index),
            other => Err(wrong("a slot", &other)),
        }
    }

    fn register(&mut self, source: SSAValue) -> Run<Vec<Option<Qubit>>> {
        match self.read(source)? {
            Value::Register(qubits) => Ok(qubits),
            other => Err(wrong("a register", &other)),
        }
    }

    /// Return the qubits of a register that has every element in place.
    fn whole(&mut self, source: SSAValue) -> Run<Vec<Qubit>> {
        let qubits = self.register(source)?.into_iter().enumerate();
        qubits
            .map(|(index, qubit)| qubit.ok_or(Failure::Lent { index }))
            .collect()
    }

    fn results(&mut self, source: SSAValue) -> Run<Vec<B::Bit>> {
        match self.read(source)? {
            Value::Bits(results) => Ok(results),
            other => Err(wrong("an array of measurement results", &other)),
        }
    }
}

/// Return `index` as a position in an array of `length` elements.
fn position(index: i64, length: usize) -> Run<usize> {
    let position = usize::try_from(index)
        .ok()
        .filter(|position| *position < length);
    position.ok_or(Failure::Index { index, length })
}

fn wrong<M>(expected: &'static str, found: &Value<M>) -> Failure {
    let found = found.kind();
    Failure::Kind { expected, found }
}
