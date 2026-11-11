//! Carry one register through nested loops and select a gate in each inner iteration.
//!
//! Both branches consume the same wire and yield its successor.
//! The branch condition comes from a classical argument.

use squin::runtime::Value;
use squin::runtime::stim::{Record, Stim};
use squin::{Kernel, KernelError};

fn main() -> Result<(), KernelError> {
    let mut kernel = Kernel::parse(include_str!("conditional_layers.kirin"))?;
    kernel.optimize()?;

    for use_h in [false, true] {
        for rounds in [0_i64, 1, 2] {
            let mut backend = Stim::default();
            let arguments = vec![Value::Bool(use_h), Value::from(rounds)];
            let returned = kernel.run("main", arguments, &mut backend)?;
            assert_eq!(
                returned,
                vec![Value::Bits(vec![Record(0), Record(1), Record(2)])]
            );

            let gate = if use_h { "H" } else { "X" };
            let layer = format!("{gate} 0\n{gate} 1\n{gate} 2\n");
            let expected = layer.repeat(rounds as usize) + "M 0 1 2\n";
            let circuit = backend.finish();
            assert_eq!(circuit, expected);
            println!("The gate is {gate}, and the round count is {rounds}:\n{circuit}");
        }
    }
    Ok(())
}
