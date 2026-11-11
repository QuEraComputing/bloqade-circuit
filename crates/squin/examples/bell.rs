//! Parse, optimize, and emit the Bell circuit through the public kernel API.

use squin::{Kernel, KernelError};

fn main() -> Result<(), KernelError> {
    // Rust embeds the source at compile time, so the executable needs no input file.
    let source = include_str!("bell.kirin");
    let mut kernel = Kernel::parse(source)?;

    println!("Before optimization:\n{}", kernel.text());
    let rewrites = kernel.optimize()?;
    println!("The rewrite count is {rewrites}.");
    println!("After optimization:\n{}", kernel.text());

    let circuit = kernel.to_stim("main")?;
    assert_eq!(circuit, "H 0\nCX 0 1\nM 0 1\n");
    println!("Stim circuit:\n{circuit}");
    Ok(())
}
