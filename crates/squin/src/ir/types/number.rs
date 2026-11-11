//! Preserve numeric widths in constants that the parser reads and the printer writes.

use std::fmt;

use kirin::parsers::chumsky::prelude::*;
use kirin::parsers::{BoxedParser, HasParser, Token, TokenInput};
use kirin_arith::{ArithType, ArithValue};

pub(super) fn parser<'t, I>() -> BoxedParser<'t, I, ArithValue>
where
    I: TokenInput<'t>,
{
    let literal = select! { Token::Int(text) | Token::Float(text) => text };
    let typed = ArithType::parser()
        .then(literal.delimited_by(just(Token::LParen), just(Token::RParen)))
        .try_map(|(ty, text), span| {
            parse_typed(ty, text).ok_or_else(|| {
                Rich::custom(
                    span,
                    format!("The literal {text} must fit {ty} and have a finite value."),
                )
            })
        });
    let default = ArithValue::parser().try_map(|value, span| {
        if finite(&value) {
            Ok(value)
        } else {
            Err(Rich::custom(span, "The float must be finite."))
        }
    });
    typed.or(default).boxed()
}

fn parse_typed(ty: ArithType, text: &str) -> Option<ArithValue> {
    macro_rules! parse {
        ($($variant:ident),+ $(,)?) => {
            match ty {
                $(ArithType::$variant => text.parse().ok().map(ArithValue::$variant),)+
            }
        };
    }
    parse!(I8, I16, I32, I64, I128, U8, U16, U32, U64, U128, F32, F64).filter(finite)
}

fn finite(value: &ArithValue) -> bool {
    match value {
        ArithValue::F32(value) => value.is_finite(),
        ArithValue::F64(value) => value.is_finite(),
        _ => true,
    }
}

pub(super) fn display(value: &ArithValue, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    match value {
        ArithValue::I64(value) => write!(f, "{value}"),
        ArithValue::F64(value) => write!(f, "{}", float_text(value)),
        ArithValue::F32(value) => write!(f, "f32({})", float_text(value)),
        ArithValue::I8(value) => write!(f, "i8({value})"),
        ArithValue::I16(value) => write!(f, "i16({value})"),
        ArithValue::I32(value) => write!(f, "i32({value})"),
        ArithValue::I128(value) => write!(f, "i128({value})"),
        ArithValue::U8(value) => write!(f, "u8({value})"),
        ArithValue::U16(value) => write!(f, "u16({value})"),
        ArithValue::U32(value) => write!(f, "u32({value})"),
        ArithValue::U64(value) => write!(f, "u64({value})"),
        ArithValue::U128(value) => write!(f, "u128({value})"),
    }
}

fn float_text(value: impl fmt::Debug) -> String {
    // The lexer requires a decimal point to recognize a float literal.
    let text = format!("{value:?}");
    match text.split_once('e') {
        Some((mantissa, exponent)) if !mantissa.contains('.') => format!("{mantissa}.0e{exponent}"),
        _ => text,
    }
}
