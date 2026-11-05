use kirin::prelude::*;
use squin::{Circuit, Stage, optimize_rz};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut pipeline = Pipeline::<Stage>::new();
    pipeline.parse(include_str!("rz.kirin"))?;
    let stage = pipeline.stage_by_name("squin").unwrap();
    let stats = optimize_rz::<Circuit, _>(&mut pipeline, stage)?;
    eprintln!(
        "The number of zero-angle removals is {}. The number of pair merges is {}.",
        stats.removed_zero, stats.merged
    );
    println!("{}", pipeline.sprint());
    Ok(())
}
