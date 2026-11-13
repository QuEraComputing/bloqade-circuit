//! Write a kernel that injects `rz(theta)` with a loop until success as ppvm `.sst` text.
//!
//! Each try prepares an ancilla in `rz(theta)|+>`, applies `cx` from the data
//! qubit to the ancilla, and measures the ancilla. If the ancilla reads 0,
//! the data qubit got `rz(theta)`, and the loop ends. If it reads 1, the
//! data qubit got `rz(-theta)`, so the next try doubles the angle. After `k`
//! failures the try uses `2^k theta`, and the loop runs 2 tries on average.
//!
//! The kernel injects a quarter turn into `|+>`, which gives `|+i>`. Then
//! `s_dag` and `h` turn `|+i>` into `|0>`, so the last measurement reads 0.
//!
//! Run `cargo run -p squin --example rz_injection -- kernel.sst` to write the
//! text to `kernel.sst`. Without an argument, the example prints the text.

use kirin::prelude::*;
use squin::Squin;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(include_str!("rz_injection.kirin"))?;
    let text = squin::emit::ppvm::emit(&pipeline, "kernel", "main")?;
    match std::env::args().nth(1) {
        Some(path) => {
            std::fs::write(&path, &text)?;
            println!("wrote {path}");
        }
        None => print!("{text}"),
    }
    Ok(())
}
