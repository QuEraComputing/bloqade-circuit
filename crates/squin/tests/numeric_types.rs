//! Check how Squin composes Kirin numeric types with its constants and program text.

use kirin::parsers::parse_ast;
use kirin::prelude::Typeof;
use squin::runtime::Value;
use squin::runtime::stim::{Record, Stim};
use squin::{ArithType, ArithValue, Kernel, KernelError, Rule, Scalar, SquinType};

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

fn run(
    parameters: &str,
    result: &str,
    body: &str,
    arguments: Vec<Value<Record>>,
) -> Result<Vec<Value<Record>>, KernelError> {
    let kernel = Kernel::parse(&program(parameters, result, body))?;
    let printed = kernel.text();
    Kernel::parse(&printed)?.run("main", arguments, &mut Stim::default())
}

#[test]
fn constants_preserve_every_numeric_width_and_range() {
    let values = [
        ArithValue::I8(i8::MIN),
        ArithValue::I16(i16::MAX),
        ArithValue::I32(i32::MIN),
        ArithValue::I64(i64::MIN),
        ArithValue::I128(i128::MIN),
        ArithValue::I128(i128::MAX),
        ArithValue::U8(u8::MAX),
        ArithValue::U16(u16::MAX),
        ArithValue::U32(u32::MAX),
        ArithValue::U64(u64::MAX),
        ArithValue::U128(u128::MAX),
        ArithValue::F32(f32::MAX),
        ArithValue::F32(f32::MIN_POSITIVE),
        ArithValue::F32(-0.0),
        ArithValue::F32(f32::from_bits(1)),
        ArithValue::F64(f64::MAX),
        ArithValue::F64(f64::MIN_POSITIVE),
        ArithValue::F64(-0.0),
        ArithValue::F64(f64::from_bits(1)),
    ];
    for value in values {
        let ty = value.type_of().to_string();
        let scalar = Scalar::Number(value.clone());
        let literal = scalar.to_string();
        assert_eq!(parse_ast::<Scalar>(&literal).unwrap(), scalar, "{literal}");
        let returned = run(
            "",
            &ty,
            &format!("%n = constant {literal} -> {ty}; ret %n;"),
            vec![],
        )
        .unwrap();
        assert_eq!(returned, [Value::Number(value)], "{literal}");
    }
}

#[test]
fn mismatched_numeric_types_fail_verification() {
    for (parameters, result, body) in [
        ("%a: i8, %b: i16", "i8", "%v = add %a, %b -> i8; ret %v;"),
        ("%a: i8, %b: i8", "u8", "%v = add %a, %b -> u8; ret %v;"),
        ("%a: i8, %b: u8", "Bool", "%v = eq %a, %b -> Bool; ret %v;"),
        ("", "i32", "%v = constant 1 -> i32; ret %v;"),
    ] {
        let Err(KernelError::Invalid(violations)) =
            Kernel::parse(&program(parameters, result, body))
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
fn numeric_literals_reject_values_outside_their_type() {
    for text in [
        "i8(128)",
        "u8(-1)",
        "u128(340282366920938463463374607431768211456)",
        "f32(1.0e39)",
        "f64(1.0e309)",
        "i32(1.5)",
    ] {
        assert!(parse_ast::<Scalar>(text).is_err(), "{text}");
    }
}

#[test]
fn old_type_names_select_the_same_numeric_types() {
    for (name, ty) in [("Int", ArithType::I64), ("Float", ArithType::F64)] {
        assert_eq!(parse_ast::<SquinType>(name).unwrap(), SquinType::Number(ty));
        assert_eq!(SquinType::Number(ty).to_string(), ty.to_string());
    }
}
