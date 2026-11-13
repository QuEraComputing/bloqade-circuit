//! Replace two rotations in a row about one axis by one rotation.
//!
//! A rule turns the first program into the second one.
//!
//! ```text
//! %a1 = rz(%x) %a0;
//! %a2 = rz(%y) %a1;
//! ```
//!
//! ```text
//! %sum = add %x, %y -> f64;
//! %a2 = rz(%sum) %a0;
//! ```
//!
//! A pattern cannot build a new statement, so a native action in Rust adds
//! the sum and the new rotation. The driver's cleanup erases the two old
//! rotations.

use kirin::prelude::*;
use kirin_arith::{Arith, ArithType};
use kirin_rewrite::PatternRule;
use kirin_wildcard::rewrite_rule;

use super::Stage;
use crate::ir::Squin;
use crate::ir::dialects::gate::{Gate, Rx, Ry, Rz};
use crate::ir::types::SquinType;
use crate::rewrite::insert_near;

/// Check that some statement reads `value`.
///
/// After a merge, the old second rotation has no use, but it stays until the
/// sweep ends. This check stops a rule from merging it a second time.
fn is_used(stage: &StageInfo<Squin>, value: SSAValue) -> bool {
    !value.expect_info(stage).uses().is_empty()
}

/// Add the sum of the angles `first` and `second` and a new rotation of `wire` next to `root`.
///
/// `make` builds the rotation from its angle, its input wire and its output.
/// The result is the output wire of the new rotation.
fn merged(
    rewriter: &mut Rewriter<'_, Squin>,
    [first, second, wire, root]: [SSAValue; 4],
    make: fn(SSAValue, SSAValue, ResultValue) -> Gate,
) -> Result<SSAValue, RewriteError> {
    let SSAKind::Result(anchor, _) = *root.expect_info(rewriter.stage()).kind() else {
        unreachable!("the pattern binds `root` to the result of a gate");
    };
    let sum = rewriter.new_result(SquinType::Number(ArithType::F64));
    let add = Arith::Add {
        lhs: first,
        rhs: second,
        result: sum,
    };
    insert_near(rewriter, anchor, Squin::Arith(add))?;
    let output = rewriter.new_result(SquinType::Wire);
    insert_near(
        rewriter,
        anchor,
        Squin::Gate(make(sum.into(), wire, output)),
    )?;
    Ok(output.into())
}

/// Write one rule for each rotation axis, and the list of those rules.
///
/// An entry `name: Rotation::op, native` merges two `Rotation` statements.
/// The native action `native` builds the new `Rotation` statement.
macro_rules! rotation_rules {
    ($($rule:ident: $gate:ident::$op:ident, $native:ident;)+) => {
        $(
            fn $native(
                rewriter: &mut Rewriter<'_, Squin>,
                first: SSAValue,
                second: SSAValue,
                wire: SSAValue,
                root: SSAValue,
            ) -> Result<SSAValue, RewriteError> {
                let make = |angle, wire, wire_out| Gate::$gate($gate { angle, wire, wire_out });
                merged(rewriter, [first, second, wire, root], make)
            }

            #[rewrite_rule(language = Squin)]
            fn $rule() {
                let g = op![$gate::$op(x, w)];
                let r = op![$gate::$op(y, g)];
                is_used(r);
                rewrite!(r, {
                    let output = $native(x, y, w, r)?;
                    replace!(r, output);
                })
            }
        )+

        /// Return every merge rule.
        pub(super) fn patterns(stage: &mut Stage) -> Vec<PatternRule<Squin>> {
            vec![$($rule(stage)),+]
        }
    };
}

rotation_rules! {
    rx_rx: Rx::rx, merged_rx;
    ry_ry: Ry::ry, merged_ry;
    rz_rz: Rz::rz, merged_rz;
}
