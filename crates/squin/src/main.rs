//! Check, optimize and emit squin programs from the command line.

use std::process::ExitCode;

use squin::{Kernel, KernelError};

const USAGE: &str = "\
Usage: squin <command> <file> [function]

Commands:
  check  Verify the program in <file>.
  opt    Run the rewrite passes and print the program.
  stim   Run the rewrite passes and print [function] as a Stim circuit.

[function] is the name of a function that takes no arguments. The default is main.";

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    let arguments: Vec<&str> = arguments.iter().map(String::as_str).collect();
    let (command, file, function) = match arguments[..] {
        [command, file] => (command, file, "main"),
        [command, file, function] => (command, file, function),
        _ => {
            eprintln!("{USAGE}");
            return ExitCode::from(2);
        }
    };
    let text = match std::fs::read_to_string(file) {
        Ok(text) => text,
        Err(error) => {
            eprintln!("squin cannot read {file}: {error}");
            return ExitCode::from(2);
        }
    };
    match run(command, &text, function) {
        Ok(Some(output)) => {
            print!("{output}");
            ExitCode::SUCCESS
        }
        Ok(None) => {
            eprintln!("{USAGE}");
            ExitCode::from(2)
        }
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}

/// Run `command` on the program `text` and return the text to print.
///
/// The result is `None` if `command` is not a command of the tool.
fn run(command: &str, text: &str, function: &str) -> Result<Option<String>, KernelError> {
    let mut kernel = Kernel::parse(text)?;
    match command {
        "check" => Ok(Some(
            "The program passes every verifier rule.\n".to_string(),
        )),
        "opt" => {
            kernel.optimize()?;
            Ok(Some(kernel.text()))
        }
        "stim" => {
            kernel.optimize()?;
            kernel.to_stim(function).map(Some)
        }
        _ => Ok(None),
    }
}
