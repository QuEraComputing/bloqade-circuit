//! Emit a GHZ preparation circuit whose register length comes from a function argument.
//!
//! The circuit prepares an equal superposition of the all-zero and all-one states.
//! The loop borrows elements `k` and `k + 1` together, then returns both before its next iteration.
//! The caller must supply a positive register length.

use squin::runtime::Value;
use squin::runtime::stim::{Record, Stim};
use squin::{Kernel, KernelError};

fn main() -> Result<(), KernelError> {
    let mut kernel = Kernel::parse(include_str!("ghz_chain.kirin"))?;
    kernel.optimize()?;

    for size in [1_i64, 2, 5] {
        let mut backend = Stim::default();
        let returned = kernel.run("main", vec![Value::from(size)], &mut backend)?;
        let records = (0..size as usize).map(Record).collect();
        assert_eq!(returned, vec![Value::Bits(records)]);

        let mut expected = String::from("H 0\n");
        for control in 0..size - 1 {
            expected.push_str(&format!("CX {control} {}\n", control + 1));
        }
        let targets: Vec<_> = (0..size).map(|index| index.to_string()).collect();
        expected.push_str(&format!("M {}\n", targets.join(" ")));

        let circuit = backend.finish();
        assert_eq!(circuit, expected);
        println!("The GHZ register length is {size}:\n{circuit}");
    }
    Ok(())
}
