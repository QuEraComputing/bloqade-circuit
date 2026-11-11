use std::fmt;

use kirin::parsers::chumsky::prelude::*;
use kirin::parsers::{BoxedParser, DirectlyParsable, HasParser, Token, TokenInput};
use kirin::prelude::Typeof;
use kirin::pretty::PrettyPrintViaDisplay;
use kirin_arith::ArithValue;

use super::SquinType;

/// Hold a numeric or Boolean constant.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Scalar {
    Number(ArithValue),
    Bool(bool),
}

impl From<ArithValue> for Scalar {
    fn from(value: ArithValue) -> Self {
        Self::Number(value)
    }
}

impl From<bool> for Scalar {
    fn from(value: bool) -> Self {
        Self::Bool(value)
    }
}

macro_rules! from_number {
    ($($ty:ty => $variant:ident),+ $(,)?) => {$(
        impl From<$ty> for Scalar {
            fn from(value: $ty) -> Self {
                Self::Number(ArithValue::$variant(value))
            }
        }
    )+};
}

from_number!(
    i8 => I8, i16 => I16, i32 => I32, i64 => I64, i128 => I128,
    u8 => U8, u16 => U16, u32 => U32, u64 => U64, u128 => U128,
    f32 => F32, f64 => F64,
);

impl Typeof<SquinType> for Scalar {
    fn type_of(&self) -> SquinType {
        match self {
            Self::Number(value) => SquinType::Number(value.type_of()),
            Self::Bool(_) => SquinType::Bool,
        }
    }
}

impl fmt::Display for Scalar {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Number(ArithValue::F64(value)) => write!(f, "{}", float_text(*value)),
            Self::Number(value) => write!(f, "{value}"),
            Self::Bool(value) => write!(f, "{value}"),
        }
    }
}

impl DirectlyParsable for Scalar {}

impl PrettyPrintViaDisplay for Scalar {}

impl<'t> HasParser<'t> for Scalar {
    type Output = Scalar;

    fn parser<I>() -> BoxedParser<'t, I, Self::Output>
    where
        I: TokenInput<'t>,
    {
        let truth = select! {
            Token::Identifier("true") => Scalar::Bool(true),
            Token::Identifier("false") => Scalar::Bool(false),
        };
        let number = ArithValue::parser().try_map(|value, span| match value {
            ArithValue::F64(float) if !float.is_finite() => {
                Err(Rich::custom(span, "The float must be finite."))
            }
            value => Ok(value),
        });
        number
            .map(Scalar::Number)
            .or(truth)
            .labelled("constant")
            .boxed()
    }
}

/// Write a float so that the lexer reads it back as a float.
///
/// The lexer needs a decimal point, and Rust writes `2.0` as `2` and `1e-7` with
/// no point. The debug form keeps the point, and the mantissa gets one here.
fn float_text(value: f64) -> String {
    let text = format!("{value:?}");
    match text.split_once('e') {
        Some((mantissa, exponent)) if !mantissa.contains('.') => format!("{mantissa}.0e{exponent}"),
        _ => text,
    }
}
