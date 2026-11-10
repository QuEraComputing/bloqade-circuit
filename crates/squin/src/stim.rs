//! Write the operations of a kernel as a Stim circuit.

use crate::gate::{Controlled, Fixed};
use crate::run::{Backend, Failure, Operation, Qubit};

/// Name one measurement by its position in the measurement record of the circuit.
///
/// The first measurement of the circuit has the position 0.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Record(pub usize);

/// Collect the lines of a Stim circuit.
///
/// The backend gives each qubit a Stim qubit index. It gives the index of a
/// freed qubit to a later allocation and resets that qubit first.
#[derive(Debug, Default)]
pub struct Stim {
    lines: Vec<String>,
    qubits: u32,
    freed: Vec<Qubit>,
    measurements: usize,
}

impl Stim {
    /// Return the circuit as text with one instruction on each line.
    pub fn finish(self) -> String {
        self.lines.iter().map(|line| format!("{line}\n")).collect()
    }

    fn instruction(&mut self, name: &str, qubits: &[Qubit]) {
        let targets: Vec<String> = qubits.iter().map(Qubit::to_string).collect();
        self.lines.push(format!("{name} {}", targets.join(" ")));
    }
}

impl Backend for Stim {
    type Bit = Record;

    fn alloc(&mut self) -> Result<Qubit, Failure> {
        if let Some(qubit) = self.freed.pop() {
            self.instruction("R", &[qubit]);
            return Ok(qubit);
        }
        let qubit = Qubit(self.qubits);
        self.qubits += 1;
        Ok(qubit)
    }

    fn free(&mut self, qubit: Qubit) -> Result<(), Failure> {
        self.freed.push(qubit);
        Ok(())
    }

    fn gate(&mut self, operation: Operation, qubits: &[Qubit]) -> Result<(), Failure> {
        let name = match operation {
            Operation::Fixed(Fixed::X) => "X",
            Operation::Fixed(Fixed::Y) => "Y",
            Operation::Fixed(Fixed::Z) => "Z",
            Operation::Fixed(Fixed::H) => "H",
            Operation::Fixed(Fixed::S) => "S",
            Operation::Fixed(Fixed::SqrtX) => "SQRT_X",
            Operation::Fixed(Fixed::SqrtY) => "SQRT_Y",
            Operation::Controlled(Controlled::X) => "CX",
            Operation::Controlled(Controlled::Y) => "CY",
            Operation::Controlled(Controlled::Z) => "CZ",
            // Stim holds Clifford gates only.
            Operation::Fixed(Fixed::T) | Operation::Rotation(..) | Operation::U3(..) => {
                let (backend, operation) = ("Stim", format!("{operation:?}"));
                return Err(Failure::Unsupported { backend, operation });
            }
        };
        self.instruction(name, qubits);
        Ok(())
    }

    fn measure(&mut self, qubits: &[Qubit]) -> Result<Vec<Record>, Failure> {
        self.instruction("M", qubits);
        let first = self.measurements;
        self.measurements += qubits.len();
        Ok((first..self.measurements).map(Record).collect())
    }

    fn reset(&mut self, qubit: Qubit) -> Result<(), Failure> {
        self.instruction("R", &[qubit]);
        Ok(())
    }
}
