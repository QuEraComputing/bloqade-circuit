use std::collections::HashMap;

use kirin::prelude::*;

use super::{Backend, Failure, Qubit, Value};
use crate::language::Squin;
use crate::verify::Verified;

/// Carry out one statement on a machine.
pub trait Execute {
    /// Read the operands of the statement from `machine` and write its results.
    ///
    /// The default is for a statement that does nothing when it runs, such as a
    /// terminator. The machine reads the operands of a terminator itself.
    fn execute<B: Backend>(&self, _machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        Ok(())
    }
}

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
    pub fn new(program: Verified<'a>, backend: &'a mut B) -> Self {
        Self {
            stage: program.stage(),
            backend,
            values: HashMap::new(),
        }
    }

    /// Return the backend that carries out the quantum operations.
    pub fn backend(&mut self) -> &mut B {
        self.backend
    }

    /// Run `block` with `arguments` and return the values that its terminator passes on.
    pub fn block(
        &mut self,
        block: Block,
        arguments: Vec<Value<B::Bit>>,
    ) -> Result<Vec<Value<B::Bit>>, Failure> {
        let parameters = block.expect_info(self.stage).arguments();
        if parameters.len() != arguments.len() {
            let (expected, found) = (parameters.len(), arguments.len());
            return Err(Failure::Arity { expected, found });
        }
        for (parameter, argument) in parameters.iter().zip(arguments) {
            self.write(*parameter, argument);
        }
        for statement in block.statements(self.stage) {
            statement.definition(self.stage).execute(self)?;
        }
        let terminator = block.terminator(self.stage);
        let passed = terminator
            .into_iter()
            .flat_map(|last| last.arguments(self.stage));
        passed.map(|value| self.read(*value)).collect()
    }

    /// Write one value to each result of `results`.
    pub fn bind(
        &mut self,
        results: &[ResultValue],
        values: Vec<Value<B::Bit>>,
    ) -> Result<(), Failure> {
        if results.len() != values.len() {
            let (expected, found) = (results.len(), values.len());
            return Err(Failure::Arity { expected, found });
        }
        for (result, value) in results.iter().zip(values) {
            self.write(*result, value);
        }
        Ok(())
    }

    pub fn write(&mut self, target: impl Into<SSAValue>, value: Value<B::Bit>) {
        self.values.insert(target.into(), value);
    }

    /// Return the value of `source`, and remove it if its type is linear.
    pub fn read(&mut self, source: impl Into<SSAValue>) -> Result<Value<B::Bit>, Failure> {
        let source = source.into();
        let value = if source.expect_info(self.stage).ty().is_linear() {
            self.values.remove(&source)
        } else {
            self.values.get(&source).cloned()
        };
        value.ok_or_else(|| Failure::Unbound(source.to_string()))
    }

    pub fn int(&mut self, source: SSAValue) -> Result<i64, Failure> {
        match self.read(source)? {
            Value::Int(value) => Ok(value),
            other => Err(other.is_not("an integer")),
        }
    }

    pub fn float(&mut self, source: SSAValue) -> Result<f64, Failure> {
        match self.read(source)? {
            Value::Float(value) => Ok(value),
            other => Err(other.is_not("a float")),
        }
    }

    pub fn wire(&mut self, source: SSAValue) -> Result<Qubit, Failure> {
        match self.read(source)? {
            Value::Wire(qubit) => Ok(qubit),
            other => Err(other.is_not("a wire")),
        }
    }

    pub fn slot(&mut self, source: SSAValue) -> Result<usize, Failure> {
        match self.read(source)? {
            Value::Slot(index) => Ok(index),
            other => Err(other.is_not("a slot")),
        }
    }

    pub fn register(&mut self, source: SSAValue) -> Result<Vec<Option<Qubit>>, Failure> {
        match self.read(source)? {
            Value::Register(qubits) => Ok(qubits),
            other => Err(other.is_not("a register")),
        }
    }

    /// Return the qubits of a register that has every element in place.
    pub fn whole(&mut self, source: SSAValue) -> Result<Vec<Qubit>, Failure> {
        let qubits = self.register(source)?.into_iter().enumerate();
        qubits
            .map(|(index, qubit)| qubit.ok_or(Failure::Lent { index }))
            .collect()
    }

    pub fn results(&mut self, source: SSAValue) -> Result<Vec<B::Bit>, Failure> {
        match self.read(source)? {
            Value::Bits(results) => Ok(results),
            other => Err(other.is_not("an array of measurement results")),
        }
    }
}

/// Return `index` as a position in an array of `length` elements.
pub fn position(index: i64, length: usize) -> Result<usize, Failure> {
    let position = usize::try_from(index)
        .ok()
        .filter(|position| *position < length);
    position.ok_or(Failure::Index { index, length })
}
