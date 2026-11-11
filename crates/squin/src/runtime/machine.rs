use std::collections::{HashMap, HashSet};

use kirin::prelude::*;

use super::{Backend, Evaluator, Execute, Failure, Value};
use crate::compiler::verify::Verified;
use crate::dialect::Squin;

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

    /// Run the function body that starts at `entry` with the caller's `arguments`.
    ///
    /// The verifier proves the types and the ownership of every value inside
    /// the program. The arguments come from outside, so this method checks
    /// their types and that no two of them own the same qubit.
    pub fn call(
        &mut self,
        entry: Block,
        arguments: Vec<Value<B::Bit>>,
    ) -> Result<Vec<Value<B::Bit>>, Failure> {
        let parameters = entry.expect_info(self.stage).arguments();
        for (index, (parameter, argument)) in parameters.iter().zip(&arguments).enumerate() {
            let expected = *parameter.expect_info(self.stage).ty();
            if !argument.matches_type(expected) {
                return Err(Failure::ArgumentType {
                    position: index + 1,
                    expected,
                    found: argument.type_name(),
                });
            }
        }
        let mut owned = HashSet::new();
        for qubit in arguments.iter().flat_map(Value::qubits) {
            if !owned.insert(qubit) {
                return Err(Failure::AliasedQubit { qubit });
            }
        }
        self.block(entry, arguments)
    }
}

impl<B: Backend> Evaluator for Machine<'_, B> {
    type Bit = B::Bit;
    type Backend = B;

    fn backend(&mut self) -> &mut B {
        self.backend
    }

    fn block(
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

    fn write(&mut self, target: impl Into<SSAValue>, value: Value<B::Bit>) {
        self.values.insert(target.into(), value);
    }

    fn read(&mut self, source: impl Into<SSAValue>) -> Result<Value<B::Bit>, Failure> {
        let source = source.into();
        let value = if source.expect_info(self.stage).ty().is_linear() {
            self.values.remove(&source)
        } else {
            self.values.get(&source).cloned()
        };
        value.ok_or_else(|| Failure::Unbound(source.to_string()))
    }
}
