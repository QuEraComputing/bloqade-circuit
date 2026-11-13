//! Print a squin kernel as Python squin code.
//!
//! Run `cargo run -p squin --example python -- file.kirin` to print the
//! function `@main` of the stage `@kernel` in `file.kirin`. Without an
//! argument, the example prints the rz injection kernel.

use kirin::prelude::*;
use squin::Squin;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let text = match std::env::args().nth(1) {
        Some(path) => std::fs::read_to_string(path)?,
        None => include_str!("rz_injection.kirin").to_string(),
    };
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline
        .parse(&text)
        .map_err(|error| format!("{error:?}"))?;
    print!(
        "{}",
        squin::emit::python::emit(&pipeline, "kernel", "main")?
    );
    Ok(())
}
