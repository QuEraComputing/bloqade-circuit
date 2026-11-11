use std::fmt;

use kirin::parsers::chumsky::prelude::*;
use kirin::parsers::{BoxedParser, DirectlyParsable, HasParser, Token, TokenInput};
use kirin::prelude::Typeof;
use kirin::pretty::PrettyPrintViaDisplay;
use kirin_arith::ArithValue;

use super::{SquinType, number};

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
            Self::Number(value) => number::display(value, f),
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
        number::parser()
            .map(Scalar::Number)
            .or(truth)
            .labelled("constant")
            .boxed()
    }
}
