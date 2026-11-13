//! Read the verifier's report for a program that consumes a wire twice.

use kirin::prelude::*;
use squin::{Rule, Squin, verify};

const SOURCE: &str = r#"
stage @kernel fn @main() -> Int;
specialize @kernel fn @main() -> Int cfg {
  ^entry() {
    %q0 = alloc;
    %q1 = circuit %q0 digraph ^g0(%q0: Wire) {
      %q1 = h %q0;
      yield %q1;
    } -> Wire;
    free %q0;
    free %q1;
    %zero = constant 0 -> Int;
    ret %zero;
  }
}
"#;

fn main() {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(SOURCE).expect("The program parses.");
    let stage = pipeline.stage_by_name("kernel").expect("The stage exists.");
    // Both `h` and the first `free` consume %q0, which violates the single-use rule.
    let Err(violations) = verify(pipeline.stage(stage).unwrap()) else {
        panic!("The verifier must reject the repeated use of %q0.");
    };
    assert!(violations.iter().any(|item| item.rule() == Rule::SingleUse));
    for violation in violations {
        println!("{:?}: {violation}", violation.rule());
    }
}
