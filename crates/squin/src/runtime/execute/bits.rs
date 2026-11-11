//! Run the bits statements.

use super::Execute;
use crate::ir::ops::{BitsGet, BitsLength, BitsOp, BitsPack};
use crate::runtime::{Evaluator, Failure, Value, position};

delegate!(BitsOp { Pack, Get, Length });

impl Execute for BitsPack {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let results = self.bits.iter().map(|bit| match machine.read(*bit)? {
            Value::Bit(result) => Ok(result),
            other => Err(other.is_not("a measurement result")),
        });
        let results = results.collect::<Result<_, _>>()?;
        machine.write(self.result, Value::Bits(results));
        Ok(())
    }
}

impl Execute for BitsGet {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let results = machine.results(self.bits)?;
        let index = position(machine.int(self.index)?, results.len())?;
        machine.write(self.bit, Value::Bit(results[index].clone()));
        Ok(())
    }
}

impl Execute for BitsLength {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let count = machine.results(self.bits)?.len();
        machine.write(self.length, Value::from(count as i64));
        Ok(())
    }
}
