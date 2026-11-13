//! Parse and print squin types in the Kirin text format.

use kirin::parsers::chumsky::prelude::*;
use kirin::parsers::{BoxedParser, DirectlyParsable, HasParser, Token, TokenInput};
use kirin::pretty::PrettyPrintViaDisplay;
use kirin_arith::ArithType;

use super::{Length, SquinType};

impl DirectlyParsable for SquinType {}

impl PrettyPrintViaDisplay for SquinType {}

impl<'t> HasParser<'t> for SquinType {
    type Output = SquinType;

    fn parser<I>() -> BoxedParser<'t, I, Self::Output>
    where
        I: TokenInput<'t>,
    {
        let count = select! { Token::Int(text) => text };
        let length = count
            .try_map(|text: &str, span| {
                text.parse()
                    .map(Length::Known)
                    .map_err(|_| Rich::custom(span, "a length is a nonnegative integer"))
            })
            .or(just(Token::QuestionMark).to(Length::Any))
            .labelled("length");
        let lent = just(Token::Semicolon)
            .ignore_then(just(Token::Identifier("lent")))
            .ignore_then(just(Token::Equal))
            .ignore_then(count)
            .try_map(|text: &str, span| {
                text.parse::<u32>()
                    .map_err(|_| Rich::custom(span, "a lent count is a nonnegative integer"))
            });
        let open = just(Token::LBracket);
        let close = just(Token::RBracket);

        let scalar = select! {
            Token::Identifier("Any") => SquinType::Any,
            Token::Identifier("Bottom") => SquinType::Bottom,
            Token::Identifier("Int") => SquinType::Number(ArithType::I64),
            Token::Identifier("Float") => SquinType::Number(ArithType::F64),
            Token::Identifier("Bool") => SquinType::Bool,
            Token::Identifier("MeasurementResult") => SquinType::MeasurementResult,
            Token::Identifier("Wire") => SquinType::Wire,
            Token::Identifier("Slot") => SquinType::Slot,
        };
        let results = just(Token::Identifier("MeasurementResults"))
            .ignore_then(length.clone().delimited_by(open.clone(), close.clone()))
            .map(SquinType::MeasurementResults);
        let register = just(Token::Identifier("Register"))
            .ignore_then(length.then(lent.or_not()).delimited_by(open, close))
            .map(|(len, lent)| SquinType::Register {
                len,
                lent: lent.unwrap_or(0),
            });

        let number = ArithType::parser().map(SquinType::Number);
        choice((number, scalar, results, register))
            .labelled("type")
            .boxed()
    }
}
