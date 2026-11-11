//! Select a function specialization from the length of an externally allocated register.
//!
//! A two-qubit register selects the Bell preparation body.
//! Other lengths select the body that applies a Hadamard gate to each qubit.

use squin::runtime::stim::{Record, Stim};
use squin::runtime::{Backend, Value};
use squin::{Kernel, KernelError};

fn main() -> Result<(), KernelError> {
    let mut kernel = Kernel::parse(include_str!("register_dispatch.kirin"))?;
    kernel.optimize()?;

    for size in [1, 2, 3] {
        let mut backend = Stim::default();
        let mut qubits = Vec::new();
        for _ in 0..size {
            qubits.push(Some(backend.alloc()?));
        }
        let returned = kernel.run("main", vec![Value::Register(qubits)], &mut backend)?;
        let records = (0..size).map(Record).collect();
        assert_eq!(returned, vec![Value::Bits(records)]);

        let mut expected = String::new();
        if size == 2 {
            expected.push_str("H 0\nCX 0 1\n");
        } else {
            for index in 0..size {
                expected.push_str(&format!("H {index}\n"));
            }
        }
        let targets: Vec<_> = (0..size).map(|index| index.to_string()).collect();
        expected.push_str(&format!("M {}\n", targets.join(" ")));

        let circuit = backend.finish();
        assert_eq!(circuit, expected);
        println!("Dispatch for Register[{size}] emits:\n{circuit}");
    }
    Ok(())
}
