//! Parse, verify, optimize and emit the Bell circuit.

use std::error::Error;

use kirin::prelude::*;
use squin::emit::stim;
use squin::rewrite::passes;
use squin::{Squin, verify};

fn main() -> Result<(), Box<dyn Error>> {
    // Rust embeds the source at compile time, so the executable needs no input file.
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(include_str!("bell.kirin"))?;
    let stage = pipeline
        .stage_by_name("kernel")
        .ok_or("The program has no @kernel stage.")?;
    if let Err(violations) = verify(pipeline.stage(stage).unwrap()) {
        return Err(format!("{violations:?}").into());
    }

    println!("Before optimization:\n{}", pipeline.sprint());
    let rewrites = passes::optimize(&mut pipeline, stage)?;
    println!("The rewrite count is {rewrites}.");
    println!("After optimization:\n{}", pipeline.sprint());

    let circuit = stim::emit(&pipeline, "kernel", "main")?;
    assert_eq!(circuit, "H 0\nCX 0 1\nM 0 1\n");
    println!("Stim circuit:\n{circuit}");
    Ok(())
}
