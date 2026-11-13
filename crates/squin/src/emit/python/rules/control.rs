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

/// Write `while True:` with the body, the carried values and `if done: break`.
///
/// This is the Python form of a do while loop: the body runs once before the
/// first test of its stop flag.
impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Repeat {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let arguments = emitter.arguments(self.body);
        let carried = emitter.carried(&arguments, &self.inputs)?;
        emitter.line("while True:");
        emitter.indented(|emitter| {
            emitter.block(self.body)?;
            let yields = emitter.yields(self.body);
            let (stop, values) = yields.split_first().ok_or_else(|| {
                PythonError::Unsupported("a `repeat` body without a stop flag".into())
            })?;
            emitter.update(&carried, values)?;
            let stop = emitter.text(*stop)?;
            emitter.line(format!("if {stop}:"));
            emitter.indented(|emitter| {
                emitter.line("break");
                Ok(())
            })
        })?;
        emitter.finish_loop(&values(&self.results), &arguments)
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
