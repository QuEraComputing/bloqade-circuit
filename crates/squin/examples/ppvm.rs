//! Write a squin kernel with a loop until success, a counted loop and a correction as ppvm `.sst` text.
//!
//! The kernel prepares qubit `b` in the one state by repeating `h` and a
//! measurement until the measurement reads one. It flips qubit `a` with two
//! `sqrt_x` gates in a counted loop, then measures `a`. If `a` reads one, a
//! `conditional` flips `b` back to zero. The last measurement of `b` reads zero.
//!
//! Run `cargo run -p squin --example ppvm -- kernel.sst` to write the text to
//! `kernel.sst`. Without an argument, the example prints the text.

use kirin::prelude::*;
use squin::Squin;

const KERNEL: &str = "stage @kernel fn @main() -> Int;
specialize @kernel fn @main() -> Int cfg {
  ^entry() {
    %zero = constant 0 -> Int;
    %one = constant 1 -> Int;
    %two = constant 2 -> Int;
    %a0 = alloc;
    %b0 = alloc;
    %b1 = repeat (%b0) do block ^prepare(%b: Wire) {
      %b2, %r = circuit %b digraph ^try(%q: Wire) {
        %q1 = h %q;
        %q2, %m = measure %q1;
        yield %q2, %m;
      } -> Wire, MeasurementResult;
      %done = is_one %r;
      yield %done, %b2;
    } -> Wire;
    %a1 = for %zero in %zero..%two step %one iter_args(%a0) do block ^flip(%i: Int, %a: Wire) {
      %a2 = circuit %a digraph ^half(%q: Wire) {
        %q1 = sqrt_x %q;
        yield %q1;
      } -> Wire;
      yield %a2;
    } -> Wire;
    %a3, %ma = circuit %a1 digraph ^read_a(%q: Wire) {
      %q1, %m = measure %q;
      yield %q1, %m;
    } -> Wire, MeasurementResult;
    %flip = is_one %ma;
    %b3 = conditional %flip (%b1) then block ^undo(%t: Wire) {
      %t1 = circuit %t digraph ^x(%q: Wire) {
        %q1 = x %q;
        yield %q1;
      } -> Wire;
      yield %t1;
    } else block ^keep(%e: Wire) {
      yield %e;
    } -> Wire;
    %b4, %mb = circuit %b3 digraph ^read_b(%q: Wire) {
      %q1, %m = measure %q;
      yield %q1, %m;
    } -> Wire, MeasurementResult;
    free %a3;
    free %b4;
    ret %zero;
  }
}
";

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline
        .parse(KERNEL)
        .map_err(|error| format!("{error:?}"))?;
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
