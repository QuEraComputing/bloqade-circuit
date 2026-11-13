//! Run emitted ppvm bytecode for the tests behind the `ppvm` feature.

use kirin::prelude::*;
use ppvm_vihaco::composite::PPVM;
use ppvm_vihaco::measurements::MeasurementOutcome;
use squin::Squin;

/// Encode `main` of the stage `@kernel`, run it once, and return the outcomes in order.
///
/// ppvm loads bytecode from a file, so the function writes the bytes to a
/// temporary file and deletes it after the load.
#[allow(dead_code)]
pub fn run(pipeline: &Pipeline<StageInfo<Squin>>) -> Vec<MeasurementOutcome> {
    let bytes = squin::emit::ppvm::bytecode(pipeline, "kernel", "main").unwrap();
    assert!(ppvm_vihaco::bytecode::is_bytecode(&bytes));
    let name = format!(
        "squin-{}-{:?}.ssb",
        std::process::id(),
        std::thread::current().id()
    );
    let path = std::env::temp_dir().join(name);
    std::fs::write(&path, &bytes).unwrap();
    let mut machine = PPVM::default();
    machine.load_bytecode_file(path.to_str().unwrap()).unwrap();
    let _ = std::fs::remove_file(&path);
    machine.run().unwrap();
    let record = machine.measurement_record();
    record
        .iter()
        .flat_map(|outcomes| outcomes.iter().copied())
        .collect()
}
