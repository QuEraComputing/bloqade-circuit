//! Write regions, branches and loops as Python `if`, `for` and `while` blocks.
//!
//! Wires keep the names of the qubits that they carry, so a branch or a loop
//! needs no assignment for a wire. A classical value that a body yields gets
//! an assignment at the end of the body.

use kirin::prelude::*;
use kirin_interpreter::dialect::Interpretable;
use kirin_scf::{For, If, Yield};

use crate::emit::python::{EmitPython, PythonEmitter, PythonError};
use crate::ir::dialects::circuit::Circuit;
use crate::ir::dialects::conditional::Conditional;
use crate::ir::dialects::repeat::Repeat;
use crate::ir::types::SquinType;

/// Write the graph nodes in dependency order with no wrapper.
impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Circuit {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let ports = self.body.expect_info(emitter.program).ports().to_vec();
        for (port, input) in ports.into_iter().zip(&self.inputs) {
            emitter.alias(port.into(), *input)?;
        }
        emitter.graph(self.body)?;
        let yields = self.body.expect_info(emitter.program).yields().to_vec();
        for (result, value) in self.results.iter().zip(yields) {
            emitter.alias((*result).into(), value)?;
        }
        Ok(())
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Conditional {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let results = values(&self.results);
        let arms = [self.then_body, self.else_body];
        emitter.branch(self.condition, arms, &self.inputs, &results)
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for If<SquinType> {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let results = values(self.results());
        let arms = [self.then_block(), self.else_block()];
        emitter.branch(self.condition(), arms, &[], &results)
    }
}

/// Write the body as a nested function and call `squin.repeat_until_success` with it.
///
/// The function takes the loop inputs as parameters. It returns the stop flag
/// and then each classical value that the body carries to the next run. The
/// call returns the classical values of the last run. A wire result keeps the
/// name of its input, because the qubit stays the same.
///
/// A Python `lambda` holds one expression, and a loop body holds statements,
/// so the emitter writes a nested `def`.
impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Repeat {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let arguments = emitter.arguments(self.body);
        let label = emitter
            .block_name(self.body)
            .unwrap_or_else(|| "attempt".into());
        let function = emitter.names.fresh(&label);
        let parameters = arguments.iter().map(|argument| emitter.name(*argument));
        let parameters = parameters.collect::<Result<Vec<_>, _>>()?;
        emitter.line(format!("def {function}({}):", parameters.join(", ")));
        emitter.indented(|emitter| {
            emitter.block(self.body)?;
            let yields = emitter.yields(self.body);
            let (stop, values) = yields.split_first().ok_or_else(|| {
                PythonError::Unsupported("a `repeat` body without a stop flag".into())
            })?;
            let mut returned = vec![emitter.text(*stop)?];
            for (argument, value) in arguments.iter().zip(values) {
                if !emitter.linear(*argument) {
                    returned.push(emitter.text(*value)?);
                }
            }
            emitter.line(format!("return {}", returned.join(", ")));
            Ok(())
        })?;
        let inputs = self.inputs.iter().map(|input| emitter.text(*input));
        let inputs: String = inputs
            .map(|input| input.map(|input| format!(", {input}")))
            .collect::<Result<_, _>>()?;
        let call = format!("squin.repeat_until_success({function}{inputs})");
        let mut classical = Vec::new();
        for (result, input) in values(&self.results).into_iter().zip(&self.inputs) {
            if emitter.linear(result) {
                emitter.alias(result, *input)?;
            } else {
                classical.push(emitter.name(result)?);
            }
        }
        match classical.is_empty() {
            true => emitter.line(call),
            false => emitter.line(format!("{} = {call}", classical.join(", "))),
        }
        Ok(())
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for For<SquinType> {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let arguments = emitter.arguments(self.body());
        let (index, rest) = arguments
            .split_first()
            .ok_or_else(|| PythonError::Unsupported("a `for` body without an index".into()))?;
        let carried = emitter.carried(rest, self.init_args())?;
        let index = emitter.name(*index)?;
        let (start, end) = (emitter.text(self.start())?, emitter.text(self.end())?);
        let step = emitter.get(self.step())?;
        let range = match step.number {
            Some(1.0) => format!("range({start}, {end})"),
            _ => format!("range({start}, {end}, {})", step.text),
        };
        emitter.line(format!("for {index} in {range}:"));
        emitter.indented(|emitter| {
            emitter.block(self.body())?;
            let yields = emitter.yields(self.body());
            emitter.update(&carried, &yields)
        })?;
        emitter.finish_loop(&values(self.results()), rest)
    }
}

/// Write nothing, because the rule that owns the block reads the yielded values.
impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Yield<SquinType> {
    fn interpret(&self, _emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        Ok(())
    }
}

fn values(results: &[ResultValue]) -> Vec<SSAValue> {
    results.iter().map(|result| (*result).into()).collect()
}
