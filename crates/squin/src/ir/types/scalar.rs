use std::fmt;
use std::hash::{Hash, Hasher};

use kirin::parsers::chumsky::prelude::*;
use kirin::parsers::{BoxedParser, DirectlyParsable, HasParser, Token, TokenInput};
use kirin::prelude::Typeof;
use kirin::pretty::PrettyPrintViaDisplay;

use super::SquinType;

/// Hold the value of a `constant` statement.
///
/// The text form selects the variant. `2` is an `Int`, `0.5` is a `Float`, and
/// `true` is a `Bool`. A `Float` must be finite, because the text format has no
/// form for an infinity.
#[derive(Clone, Copy, Debug)]
pub enum Scalar {
    Int(i64),
    Float(f64),
    Bool(bool),
}

/// Compare floats by their bits, so that equality agrees with the hash.
impl PartialEq for Scalar {
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (Scalar::Int(left), Scalar::Int(right)) => left == right,
            (Scalar::Float(left), Scalar::Float(right)) => left.to_bits() == right.to_bits(),
            (Scalar::Bool(left), Scalar::Bool(right)) => left == right,
            _ => false,
        }
    }
}

impl Eq for Scalar {}

impl Hash for Scalar {
    fn hash<H: Hasher>(&self, state: &mut H) {
        std::mem::discriminant(self).hash(state);
        match self {
            Scalar::Int(value) => value.hash(state),
            Scalar::Float(value) => value.to_bits().hash(state),
            Scalar::Bool(value) => value.hash(state),
        }
    }
}

impl From<i64> for Scalar {
    fn from(value: i64) -> Self {
        Scalar::Int(value)
    }
}

impl From<f64> for Scalar {
    fn from(value: f64) -> Self {
        Scalar::Float(value)
    }
}

impl From<bool> for Scalar {
    fn from(value: bool) -> Self {
        Scalar::Bool(value)
    }
}

impl Typeof<SquinType> for Scalar {
    fn type_of(&self) -> SquinType {
        match self {
            Scalar::Int(_) => SquinType::Int,
            Scalar::Float(_) => SquinType::Float,
            Scalar::Bool(_) => SquinType::Bool,
        }
    }
}

impl fmt::Display for Scalar {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Scalar::Int(value) => write!(f, "{value}"),
            Scalar::Bool(value) => write!(f, "{value}"),
            Scalar::Float(value) => {
                // The lexer reads a float only if the text has a decimal point.
                // Rust prints 1e-7 with no point, so the mantissa gets one here.
                let text = format!("{value:?}");
                match text.split_once('e') {
                    Some((mantissa, exponent)) if !mantissa.contains('.') => {
                        write!(f, "{mantissa}.0e{exponent}")
                    }
                    _ => write!(f, "{text}"),
                }
            }
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
        let integer = select! { Token::Int(text) => text }.try_map(|text: &str, span| {
            let value = text.parse().map(Scalar::Int);
            value.map_err(|_| Rich::custom(span, "the integer does not fit in 64 bits"))
        });
        let float = select! { Token::Float(text) => text }.try_map(|text: &str, span| {
            let value = text
                .parse::<f64>()
                .map_err(|_| Rich::custom(span, "The text must contain a float."))?;
            if !value.is_finite() {
                return Err(Rich::custom(span, "The float must be finite."));
            }
            Ok(Scalar::Float(value))
        });
        let truth = select! {
            Token::Identifier("true") => Scalar::Bool(true),
            Token::Identifier("false") => Scalar::Bool(false),
        };
        choice((float, integer, truth)).labelled("constant").boxed()
    }
}
