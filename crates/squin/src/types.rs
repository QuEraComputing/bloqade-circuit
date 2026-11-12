use kirin::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq, Serialize, Deserialize)]
pub enum RegisterLength {
    Known { length: u64 },
    Dynamic,
}

#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq, Serialize, Deserialize)]
pub enum Type {
    Wire,
    Register { length: RegisterLength },
    Bit,
    Int,
    Unit,
}

impl Type {
    pub const fn register(length: u64) -> Self {
        Self::Register {
            length: RegisterLength::Known { length },
        }
    }

    pub const fn dynamic_register() -> Self {
        Self::Register {
            length: RegisterLength::Dynamic,
        }
    }

    pub const fn is_linear(self) -> bool {
        matches!(self, Self::Wire | Self::Register { .. })
    }
}

impl Placeholder for Type {
    fn placeholder() -> Self {
        Self::Unit
    }
}

impl std::fmt::Display for RegisterLength {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Known { length } => write!(f, "{length}"),
            Self::Dynamic => f.write_str("?"),
        }
    }
}

impl std::fmt::Display for Type {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Wire => f.write_str("Wire"),
            Self::Register { length } => write!(f, "Register<{length}>"),
            Self::Bit => f.write_str("Bit"),
            Self::Int => f.write_str("Int"),
            Self::Unit => f.write_str("Unit"),
        }
    }
}

impl<'t> HasParser<'t> for RegisterLength {
    type Output = Self;

    fn parser<I: TokenInput<'t>>() -> BoxedParser<'t, I, Self> {
        u64::parser()
            .map(|length| Self::Known { length })
            .or(just(Token::QuestionMark).to(Self::Dynamic))
            .boxed()
    }
}

impl<'t> HasParser<'t> for Type {
    type Output = Self;

    fn parser<I: TokenInput<'t>>() -> BoxedParser<'t, I, Self> {
        let scalar = select! {
            Token::Identifier("Wire") => Self::Wire,
            Token::Identifier("Bit") => Self::Bit,
            Token::Identifier("Int") => Self::Int,
            Token::Identifier("Unit") => Self::Unit,
        };
        let register = just(Token::Identifier("Register"))
            .ignore_then(just(Token::LAngle))
            .ignore_then(RegisterLength::parser())
            .then_ignore(just(Token::RAngle))
            .map(|length| Self::Register { length });
        scalar.or(register).boxed()
    }
}

impl DirectlyParsable for RegisterLength {}
impl DirectlyParsable for Type {}
impl PrettyPrintViaDisplay for RegisterLength {}
impl PrettyPrintViaDisplay for Type {}

impl Typeof<Type> for i64 {
    fn type_of(&self) -> Type {
        Type::Int
    }
}
