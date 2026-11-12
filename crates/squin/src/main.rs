//! Check, optimize and emit squin programs from the command line.

use std::error::Error;
use std::process::ExitCode;

use kirin::prelude::*;
use squin::emit::stim;
use squin::rewrite::passes;
use squin::{Squin, verify};

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
    if !["check", "opt", "stim"].contains(&command) {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    }
    let text = match std::fs::read_to_string(file) {
        Ok(text) => text,
        Err(error) => {
            eprintln!("squin cannot read {file}: {error}");
            return ExitCode::from(2);
        }
    };
    match run(command, &text, function) {
        Ok(output) => {
            print!("{output}");
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}

/// Run `command` on the program `text` and return the text to print.
fn run(command: &str, text: &str, function: &str) -> Result<String, Box<dyn Error>> {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(text)?;
    let stages: Vec<(CompileStage, Option<GlobalSymbol>)> = pipeline.stage_names().collect();
    let [(stage, Some(symbol))] = stages[..] else {
        return Err("The program must declare one named stage.".into());
    };
    let name = pipeline.resolve(symbol).unwrap_or_default().to_string();
    let program = pipeline
        .stage(stage)
        .ok_or("The stage holds no squin program.")?;
    if let Err(violations) = verify(program) {
        let lines: Vec<String> = violations.iter().map(ToString::to_string).collect();
        return Err(lines.join("\n").into());
    }
    if command == "check" {
        return Ok("The program passes every verifier rule.\n".to_string());
    }
    passes::optimize(&mut pipeline, stage)?;
    match command {
        "opt" => Ok(pipeline.sprint()),
        _ => Ok(stim::emit(&pipeline, &name, function)?),
    }
}
