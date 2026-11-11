//! Run the qubit statements.

use super::Execute;
use crate::ir::dialects::qubit::{Alloc, Free, Measure, QubitOp, Reset};
use crate::runtime::{Backend, Evaluator, Failure, Value};

delegate!(QubitOp {
    Alloc,
    Free,
    Measure,
    Reset
});

impl Execute for Alloc {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let qubit = machine.backend().alloc()?;
        machine.write(self.wire, Value::Wire(qubit));
        Ok(())
    }
}

impl Execute for Free {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let qubit = machine.wire(self.wire)?;
        machine.backend().free(qubit)
    }
}

impl Execute for Measure {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let qubit = machine.wire(self.wire)?;
        let mut results = machine.backend().measure(&[qubit])?;
        let (expected, found) = (1, results.len());
        let result = results.pop().ok_or(Failure::Arity { expected, found })?;
        machine.write(self.wire_out, Value::Wire(qubit));
        machine.write(self.bit, Value::Bit(result));
        Ok(())
    }
}

impl Execute for Reset {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let qubit = machine.wire(self.wire)?;
        machine.backend().reset(qubit)?;
        machine.write(self.wire_out, Value::Wire(qubit));
        Ok(())
    }
}
