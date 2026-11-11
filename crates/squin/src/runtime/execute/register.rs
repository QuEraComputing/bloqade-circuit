//! Run the register statements.

use super::Execute;
use crate::ir::dialects::register::{
    AllocRegister, Borrow, FreeRegister, Join, LengthOf, MeasureRegister, Pack, RegisterOp,
    Release, Replace, Split,
};
use crate::runtime::{Backend, Evaluator, Failure, Value, position};

delegate!(RegisterOp {
    AllocRegister,
    FreeRegister,
    Pack,
    Split,
    Join,
    LengthOf,
    MeasureRegister,
    Borrow,
    Release,
    Replace,
});

impl Execute for AllocRegister {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let size = machine.int(self.size)?;
        let count = usize::try_from(size).map_err(|_| Failure::Size(size))?;
        let qubits = (0..count).map(|_| machine.backend().alloc().map(Some));
        let qubits = qubits.collect::<Result<_, _>>()?;
        machine.write(self.register, Value::Register(qubits));
        Ok(())
    }
}

impl Execute for FreeRegister {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        for qubit in machine.whole(self.register)? {
            machine.backend().free(qubit)?;
        }
        Ok(())
    }
}

impl Execute for Pack {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let qubits = self.wires.iter().map(|wire| machine.wire(*wire).map(Some));
        let qubits = qubits.collect::<Result<_, _>>()?;
        machine.write(self.register, Value::Register(qubits));
        Ok(())
    }
}

impl Execute for Split {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let mut qubits = machine.register(self.register)?;
        let (index, length) = (machine.int(self.index)?, qubits.len());
        let cut = usize::try_from(index).ok().filter(|cut| *cut <= length);
        let rest = qubits.split_off(cut.ok_or(Failure::Index { index, length })?);
        machine.write(self.before, Value::Register(qubits));
        machine.write(self.after, Value::Register(rest));
        Ok(())
    }
}

impl Execute for Join {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let mut qubits = machine.register(self.first)?;
        qubits.extend(machine.register(self.second)?);
        machine.write(self.register, Value::Register(qubits));
        Ok(())
    }
}

impl Execute for LengthOf {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let qubits = machine.register(self.register)?;
        machine.write(self.length, Value::Int(qubits.len() as i64));
        machine.write(self.register_out, Value::Register(qubits));
        Ok(())
    }
}

impl Execute for MeasureRegister {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let qubits = machine.whole(self.register)?;
        let results = machine.backend().measure(&qubits)?;
        let qubits = qubits.into_iter().map(Some).collect();
        machine.write(self.register_out, Value::Register(qubits));
        machine.write(self.bits, Value::Bits(results));
        Ok(())
    }
}

impl Execute for Borrow {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let mut qubits = machine.register(self.register)?;
        let index = position(machine.int(self.index)?, qubits.len())?;
        let qubit = qubits[index].take().ok_or(Failure::Lent { index })?;
        machine.write(self.register_out, Value::Register(qubits));
        machine.write(self.slot, Value::Slot(index));
        machine.write(self.wire, Value::Wire(qubit));
        Ok(())
    }
}

impl Execute for Release {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let mut qubits = machine.register(self.register)?;
        let index = machine.slot(self.slot)?;
        let qubit = machine.wire(self.wire)?;
        let length = qubits.len();
        let element = qubits.get_mut(index).ok_or(Failure::Index {
            index: index as i64,
            length,
        })?;
        *element = Some(qubit);
        machine.write(self.register_out, Value::Register(qubits));
        Ok(())
    }
}

impl Execute for Replace {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let mut qubits = machine.register(self.register)?;
        let index = position(machine.int(self.index)?, qubits.len())?;
        let old = qubits[index].replace(machine.wire(self.wire)?);
        machine.write(self.register_out, Value::Register(qubits));
        machine.write(
            self.wire_out,
            Value::Wire(old.ok_or(Failure::Lent { index })?),
        );
        Ok(())
    }
}
