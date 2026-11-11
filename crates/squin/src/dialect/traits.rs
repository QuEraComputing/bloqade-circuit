//! Describe the type rules, qubit continuity, control flow, and borrows of each statement.

use kirin::prelude::{Block, CFG, Lattice, ResultValue, SSAValue, Signature};
use smallvec::SmallVec;

use super::semantics::{Backend, Failure, Qubit, Value};
use super::types::{Length, SquinType};

/// Hold the pairs of a statement. Most statements have one pair or two.
pub type Pairs = SmallVec<[(SSAValue, ResultValue); 2]>;

/// Tell which result of a statement continues which linear operand.
///
/// A pair `(operand, result)` states that both values name the same qubit or
/// the same register. For example, `h %a -> Wire` pairs `%a` with its result.
pub trait Threads {
    /// Return each linear operand with the result that continues it.
    ///
    /// The default is for a statement that continues none of its operands.
    fn threads(&self) -> Pairs {
        Pairs::new()
    }
}

/// State the types that a statement needs for its operands and results.
pub trait Typed {
    /// Check the types of the statement and record each mismatch in `typing`.
    ///
    /// The default is for a statement that accepts every type.
    fn check<C: TypeCheck>(&self, _typing: &mut C) {}
}

/// Give a type rule the types of the program and collect its findings.
///
/// The verifier implements this trait. A statement uses the provided methods,
/// which build on the required ones.
pub trait TypeCheck {
    /// Return the type of `value`.
    fn ty(&self, value: SSAValue) -> SquinType;

    /// Return the values that the terminator of `block` passes on.
    fn yields(&self, block: Block) -> Vec<SSAValue>;

    /// Return the arguments of `block`.
    fn arguments(&self, block: Block) -> Vec<SSAValue>;

    /// Return the blocks of the function body `body`, with the entry block first.
    fn body_blocks(&self, body: CFG) -> Vec<Block>;

    /// Record that `value` has another type than the type `expected` names.
    fn report_type(&mut self, value: SSAValue, expected: String);

    /// Record that a block passes on `found` values where `expected` must arrive.
    fn report_arity(&mut self, expected: usize, found: usize);

    /// Record that `value` has another type than the type `expected` names.
    fn fail(&mut self, value: impl Into<SSAValue>, expected: impl Into<String>) {
        self.report_type(value.into(), expected.into());
    }

    /// Return whether `found` equals `expected`, and record a violation if it does not.
    fn arity(&mut self, expected: usize, found: usize) -> bool {
        if expected != found {
            self.report_arity(expected, found);
        }
        expected == found
    }

    /// Require `value` to fit `expected` and keep its ownership rule.
    fn expect(&mut self, value: impl Into<SSAValue>, expected: SquinType) {
        let value = value.into();
        if !fits(self.ty(value), expected) {
            self.fail(value, expected.to_string());
        }
    }

    /// Require each value to fit `expected` and keep its ownership rule.
    fn each<V: Into<SSAValue>>(
        &mut self,
        values: impl IntoIterator<Item = V>,
        expected: SquinType,
    ) {
        for value in values {
            self.expect(value, expected);
        }
    }

    /// Require the type of `value` to be exactly `expected`.
    fn exact(&mut self, value: impl Into<SSAValue>, expected: SquinType) {
        let value = value.into();
        if self.ty(value) != expected {
            self.fail(value, expected.to_string());
        }
    }

    /// Require `computed` to fit the declared type of `value` and keep its ownership rule.
    fn covers(&mut self, value: impl Into<SSAValue>, computed: SquinType) {
        let value = value.into();
        if !fits(computed, self.ty(value)) {
            self.fail(value, computed.to_string());
        }
    }

    /// Require `value` to be a register with every element in place.
    fn whole(&mut self, value: impl Into<SSAValue>) {
        self.expect(value, SquinType::register(Length::Any));
    }

    /// Return the length and the lent count of `value` if it is a register.
    fn register(&mut self, value: impl Into<SSAValue>) -> Option<(Length, u32)> {
        let value = value.into();
        match self.ty(value) {
            SquinType::Register { len, lent } => Some((len, lent)),
            _ => {
                self.fail(value, "a register");
                None
            }
        }
    }

    /// Require each value of `sources` to fit the type of its `targets` value.
    fn flows<S, T>(&mut self, sources: &[S], targets: &[T])
    where
        S: Copy + Into<SSAValue>,
        T: Copy + Into<SSAValue>,
    {
        if !self.arity(targets.len(), sources.len()) {
            return;
        }
        for (source, target) in sources.iter().zip(targets) {
            let expected = self.ty((*target).into());
            self.expect(*source, expected);
        }
    }

    /// Check the entry arguments and the return values against the function signature.
    fn function(&mut self, body: CFG, signature: &Signature<SquinType>) {
        let blocks = self.body_blocks(body);
        let Some(&entry) = blocks.first() else {
            self.arity(1, 0);
            return;
        };
        let arguments = self.arguments(entry);
        if self.arity(signature.params().len(), arguments.len()) {
            for (argument, expected) in arguments.iter().zip(signature.params()) {
                self.exact(*argument, *expected);
            }
        }
        for block in blocks {
            let returned = self.yields(block);
            if self.arity(1, returned.len()) {
                self.expect(returned[0], *signature.ret());
            }
        }
    }
}

/// Check whether execution can pass a value from `source` to `target`.
fn fits(source: SquinType, target: SquinType) -> bool {
    // Bottom describes a value that execution cannot produce.
    // The evaluator copies non-linear values, so a type change must preserve the ownership rule.
    source != SquinType::Bottom
        && source.is_linear() == target.is_linear()
        && source.is_subseteq(&target)
}

/// Carry out one statement on an evaluator.
pub trait Execute {
    /// Read the operands of the statement from `machine` and write its results.
    ///
    /// The default is for a statement that does nothing when it runs, such as a
    /// terminator. The evaluator reads the operands of a terminator itself.
    fn execute<E: Evaluator>(&self, _machine: &mut E) -> Result<(), Failure> {
        Ok(())
    }
}

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

/// Tell how a statement runs the blocks that it owns.
pub enum Nesting<'a> {
    /// The statement owns no block.
    Flat,
    /// The statement runs exactly one of the two blocks, as an `if` does.
    Arms([Block; 2]),
    /// The statement runs `body` any number of times, as a `for` does.
    ///
    /// `initial` holds the values that the first run receives after the loop
    /// index. Result `i` of the statement continues `initial[i]`.
    Loop {
        body: Block,
        initial: &'a [SSAValue],
    },
}

/// Describe a statement that takes an element out of a register or puts it back.
pub enum Lending {
    /// The statement lends the element at `index` to `wire` and makes `slot`.
    Borrow {
        register: SSAValue,
        index: SSAValue,
        register_out: ResultValue,
        slot: ResultValue,
        wire: ResultValue,
    },
    /// The statement consumes `slot` and fills its element with `wire`.
    Release {
        register: SSAValue,
        slot: SSAValue,
        wire: SSAValue,
    },
}

/// Describe a statement whose result is an integer that the verifier can compare.
pub enum Offset {
    /// The result is this constant.
    Constant(i64),
    /// The result is the sum of the two values.
    Sum(SSAValue, SSAValue),
    /// The result is the first value minus the second value.
    Difference(SSAValue, SSAValue),
}

/// Give the verifier the facts about a statement that its rules need.
///
/// Each default is for a statement that owns no block, lends no element and
/// gives no integer that the verifier can compare.
pub trait Structure {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Flat
    }

    fn lending(&self) -> Option<Lending> {
        None
    }

    fn offset(&self) -> Option<Offset> {
        None
    }
}
