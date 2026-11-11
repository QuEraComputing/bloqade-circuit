//! Read the verifier's report for a program that consumes a wire twice.

use squin::{Kernel, KernelError, Rule};

const SOURCE: &str = r#"
stage @kernel fn @main() -> Int;
specialize @kernel fn @main() -> Int cfg {
  ^entry() {
    %q0 = alloc;
    %q1 = h %q0;
    free %q0;
    free %q1;
    %zero = constant 0 -> Int;
    ret %zero;
  }
}
"#;

fn main() -> Result<(), KernelError> {
    // Both `h` and the first `free` consume %q0, which violates the single-use rule.
    match Kernel::parse(SOURCE) {
        Err(KernelError::Invalid(violations)) => {
            assert!(violations.iter().any(|item| item.rule() == Rule::SingleUse));
            for violation in violations {
                println!("{:?}: {violation}", violation.rule());
            }
        }
        Err(error) => return Err(error),
        Ok(_) => panic!("The verifier must reject the repeated use of %q0."),
    }
    Ok(())
}
