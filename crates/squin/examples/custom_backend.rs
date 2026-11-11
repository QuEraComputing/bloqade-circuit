//! Trace quantum operations while the Stim backend writes a circuit.

use squin::runtime::stim::{Record, Stim};
use squin::runtime::{Backend, Failure, Operation, Qubit, Value};
use squin::{Kernel, KernelError};

#[derive(Default)]
struct Trace {
    stim: Stim,
    gates: usize,
}

impl Backend for Trace {
    // Stim represents a measurement result by its position in the measurement record.
    type Bit = Record;

    fn alloc(&mut self) -> Result<Qubit, Failure> {
        let qubit = self.stim.alloc()?;
        println!("Allocate qubit {qubit}.");
        Ok(qubit)
    }

    fn free(&mut self, qubit: Qubit) -> Result<(), Failure> {
        println!("Free qubit {qubit}.");
        self.stim.free(qubit)
    }

    fn gate(&mut self, operation: Operation, qubits: &[Qubit]) -> Result<(), Failure> {
        self.stim.gate(operation, qubits)?;
        self.gates += 1;
        println!("Apply {operation:?} to {qubits:?}.");
        Ok(())
    }

    fn measure(&mut self, qubits: &[Qubit]) -> Result<Vec<Record>, Failure> {
        println!("Measure {qubits:?}.");
        self.stim.measure(qubits)
    }

    fn reset(&mut self, qubit: Qubit) -> Result<(), Failure> {
        println!("Reset qubit {qubit}.");
        self.stim.reset(qubit)
    }
}

fn main() -> Result<(), KernelError> {
    let mut kernel = Kernel::parse(include_str!("bell.kirin"))?;
    kernel.optimize()?;
    let mut backend = Trace::default();

    // The machine computes register indices and calls these backend methods with qubit identifiers.
    let returned = kernel.run("main", Vec::new(), &mut backend)?;
    assert_eq!(returned, vec![Value::Bits(vec![Record(0), Record(1)])]);
    assert_eq!(backend.gates, 2);
    println!("The kernel returned measurement record positions: {returned:?}");
    println!("The backend received {} gates.", backend.gates);
    println!("Stim circuit:\n{}", backend.stim.finish());
    Ok(())
}
