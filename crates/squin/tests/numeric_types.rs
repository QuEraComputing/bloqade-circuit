//! Check how Squin composes Kirin numeric types with its constants and program text.

mod common;

use kirin::parsers::parse_ast;

use squin::{ArithType, Rule, SquinType};

fn program(parameters: &str, result: &str, body: &str) -> String {
    let types: Vec<_> = parameters
        .split(',')
        .filter_map(|parameter| parameter.split_once(':').map(|(_, ty)| ty.trim()))
        .collect();
    format!(
        "stage @kernel fn @main({}) -> {result};
         specialize @kernel fn @main({}) -> {result} cfg {{
           ^entry({parameters}) {{ {body} }}
         }}",
        types.join(", "),
        types.join(", ")
    )
}

#[test]
fn mismatched_numeric_types_fail_verification() {
    for (parameters, result, body) in [
        ("%a: i8, %b: i16", "i8", "%v = add %a, %b -> i8; ret %v;"),
        ("%a: i8, %b: i8", "u8", "%v = add %a, %b -> u8; ret %v;"),
        ("%a: i8, %b: u8", "Bool", "%v = eq %a, %b -> Bool; ret %v;"),
        ("", "i32", "%v = constant 1 -> i32; ret %v;"),
    ] {
        let Err(common::Rejected::Invalid(violations)) =
            common::check(&program(parameters, result, body))
        else {
            panic!("The verifier must reject mismatched numeric types.");
        };
        assert!(
            violations
                .iter()
                .any(|violation| violation.rule() == Rule::Type)
        );
    }
}

#[test]
fn old_type_names_select_the_same_numeric_types() {
    for (name, ty) in [("Int", ArithType::I64), ("Float", ArithType::F64)] {
        assert_eq!(parse_ast::<SquinType>(name).unwrap(), SquinType::Number(ty));
        assert_eq!(SquinType::Number(ty).to_string(), ty.to_string());
    }
}
