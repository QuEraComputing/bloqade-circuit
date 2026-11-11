//! Compare type information and the ownership rules that constrain its use.

use kirin::parsers::parse_ast;
use kirin::prelude::{Lattice, Placeholder, Typeof};
use kirin_arith::ArithType;
use squin::runtime::Value;
use squin::{ArithValue, Length, Scalar, SquinType};

fn main() {
    let two = SquinType::register(Length::Known(2));
    let three = SquinType::register(Length::Known(3));
    let unknown_length = SquinType::register(Length::Any);

    // A join keeps the information that both types guarantee.
    assert_eq!(two.join(&three), unknown_length);
    println!("The join of {two} and {three} is {}.", two.join(&three));

    // A meet describes values that fit both types.
    assert_eq!(two.meet(&unknown_length), two);
    assert_eq!(two.meet(&three), SquinType::Bottom);
    println!("The meet of {two} and {three} is {}.", two.meet(&three));

    let borrowed = SquinType::Register {
        len: Length::Known(2),
        lent: 1,
    };
    assert!(!borrowed.is_subseteq(&two));
    let text = borrowed.to_string();
    assert_eq!(parse_ast::<SquinType>(&text).unwrap(), borrowed);
    println!("A register with one open borrow has type {text}.");

    let angle = Scalar::from(0.25);
    assert_eq!(angle.type_of(), SquinType::Number(ArithType::F64));
    println!("The constant {angle} has type {}.", angle.type_of());

    let count = Scalar::Number(ArithValue::U32(7));
    assert_eq!(count.type_of(), SquinType::Number(ArithType::U32));
    assert_eq!(parse_ast::<Scalar>(&count.to_string()).unwrap(), count);
    let argument: Value<bool> = Value::from(7_u32);
    assert_eq!(argument, Value::Number(ArithValue::U32(7)));
    println!("The constant {count} uses Kirin's u32 type and value.");

    // The verifier also checks ownership whenever it passes a value between types.
    assert!(SquinType::Wire.is_subseteq(&SquinType::Any));
    assert!(SquinType::Wire.is_linear());
    assert!(!SquinType::Any.is_linear());
    println!(
        "The verifier rejects passing a Wire as Any because that would lose its ownership rule."
    );

    // Builders use this temporary type when neither the declaration nor the caller supplies a result type.
    assert_eq!(SquinType::placeholder(), SquinType::Any);
    println!(
        "Gate builders declare Wire results. Pack builders compute the length from the operand count."
    );
    println!(
        "Register results that depend on operand types still need explicit types before verification."
    );
}
