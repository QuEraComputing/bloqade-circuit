//! Run the gate statements.

use super::Execute;
use crate::ir::dialects::gate::for_each_gate;
use crate::ir::ops::*;
use crate::ir::traits::Threads;
use crate::runtime::{Backend, Evaluator, Failure, Operation, Value};

/// Hand each gate to the backend with the values of its angles and the qubits of its wires.
macro_rules! executed {
    ($($name:ident $(($($angle:ident),+))?;)+) => {
        $(impl Execute for $name {
            fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
                $($(let $angle = machine.float(self.$angle)?;)+)?
                let operation = Operation::$name $(($($angle),+))?;
                let threads = self.threads();
                let qubits = threads.iter().map(|(wire, _)| machine.wire(*wire));
                let qubits = qubits.collect::<Result<Vec<_>, _>>()?;
                machine.backend().gate(operation, &qubits)?;
                for ((_, wire_out), qubit) in threads.iter().zip(qubits) {
                    machine.write(*wire_out, Value::Wire(qubit));
                }
                Ok(())
            }
        })+

        delegate!(Gate { $($name),+ });
    };
}

for_each_gate!(executed);
