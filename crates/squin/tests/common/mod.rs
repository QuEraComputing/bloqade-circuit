//! Share the kernel parser of the squin tests.

use kirin::prelude::*;
use squin::Squin;

/// Parse a kernel with the parameters `parameters` and the statements `body`.
///
/// `parameters` is a list such as `"%c: Bool, %a: Float"`. The kernel has one
/// function, which returns an `Int`.
pub fn kernel(parameters: &str, body: &str) -> Pipeline<StageInfo<Squin>> {
    let types: Vec<&str> = parameters
        .split(',')
        .filter_map(|parameter| parameter.split(':').nth(1))
        .map(str::trim)
        .collect();
    let signature = format!("fn @main({}) -> Int", types.join(", "));
    let program = format!(
        "stage @kernel {signature};\n\
         specialize @kernel {signature} cfg {{\n  ^entry({parameters}) {{\n{body}\n  }}\n}}\n"
    );
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    if let Err(error) = pipeline.parse(&program) {
        panic!("the kernel must parse: {error:?}\n{program}");
    }
    pipeline
}
