//! Write nothing for classical statements, because a Stim circuit holds no classical values.

use kirin_arith::Arith;
use kirin_bitwise::Bitwise;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_function::{Function, Return};

use super::nothing;
use crate::ir::dialects::measurement::*;
use crate::ir::types::{Scalar, SquinType};

nothing!(
    Constant<Scalar, SquinType>,
    Arith<SquinType>,
    Cmp<SquinType>,
    Bitwise<SquinType>,
    Function<SquinType>,
    Return<SquinType>,
    PackResults,
    GetResult,
    ResultsLength,
    IsZero,
    IsOne,
    IsLost,
);
