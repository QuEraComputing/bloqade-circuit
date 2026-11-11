//! Define the context that a statement reads and writes values through while it runs.

use kirin::prelude::{Block, ResultValue, SSAValue};

use super::{Backend, Failure, Qubit, Value};

/// Give a statement the values of the program and the backend while it runs.
///
/// The runtime `Machine` implements this trait. A statement uses the provided
/// methods, which build on the required ones.
pub trait Evaluator {
    /// The value that the backend gives for one measurement.
    type Bit: Clone;
    /// The backend that carries out the quantum operations.
    type Backend: Backend<Bit = Self::Bit>;

    /// Return the backend that carries out the quantum operations.
    fn backend(&mut self) -> &mut Self::Backend;

    /// Return the value of `source`, and remove it if its type is linear.
    fn read(&mut self, source: impl Into<SSAValue>) -> Result<Value<Self::Bit>, Failure>;

    /// Give `target` the value `value`.
    fn write(&mut self, target: impl Into<SSAValue>, value: Value<Self::Bit>);

    /// Run `block` with `arguments` and return the values that its terminator passes on.
    fn block(
        &mut self,
        block: Block,
        arguments: Vec<Value<Self::Bit>>,
    ) -> Result<Vec<Value<Self::Bit>>, Failure>;

    /// Write one value to each result of `results`.
    fn bind(
        &mut self,
        results: &[ResultValue],
        values: Vec<Value<Self::Bit>>,
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

    fn int(&mut self, source: SSAValue) -> Result<i64, Failure> {
        match self.read(source)? {
            Value::Int(value) => Ok(value),
            other => Err(other.is_not("an integer")),
        }
    }

    fn float(&mut self, source: SSAValue) -> Result<f64, Failure> {
        match self.read(source)? {
            Value::Float(value) => Ok(value),
            other => Err(other.is_not("a float")),
        }
    }

    fn wire(&mut self, source: SSAValue) -> Result<Qubit, Failure> {
        match self.read(source)? {
            Value::Wire(qubit) => Ok(qubit),
            other => Err(other.is_not("a wire")),
        }
    }

    fn slot(&mut self, source: SSAValue) -> Result<usize, Failure> {
        match self.read(source)? {
            Value::Slot(index) => Ok(index),
            other => Err(other.is_not("a slot")),
        }
    }

    fn register(&mut self, source: SSAValue) -> Result<Vec<Option<Qubit>>, Failure> {
        match self.read(source)? {
            Value::Register(qubits) => Ok(qubits),
            other => Err(other.is_not("a register")),
        }
    }

    /// Return the qubits of a register that has every element in place.
    fn whole(&mut self, source: SSAValue) -> Result<Vec<Qubit>, Failure> {
        let qubits = self.register(source)?.into_iter().enumerate();
        qubits
            .map(|(index, qubit)| qubit.ok_or(Failure::Lent { index }))
            .collect()
    }

    fn results(&mut self, source: SSAValue) -> Result<Vec<Self::Bit>, Failure> {
        match self.read(source)? {
            Value::Bits(results) => Ok(results),
            other => Err(other.is_not("an array of measurement results")),
        }
    }
}
