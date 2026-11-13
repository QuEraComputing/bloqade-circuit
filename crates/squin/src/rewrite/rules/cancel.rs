//! Remove two gates in a row whose product is the identity.
//!
//! A rule turns the first program into the second one.
//!
//! ```text
//! %a1 = h %a0;
//! %a2 = h %a1;
//! free %a2;
//! ```
//!
//! ```text
//! free %a0;
//! ```
//!
//! The rule moves the uses of the last result to the first operand. The
//! driver's cleanup then erases both gates, because nothing reads them.

use kirin_rewrite::PatternRule;
use kirin_wildcard::rewrite_rule;

use super::Stage;
use crate::ir::Squin;
use crate::ir::dialects::gate::{
    CX, CY, CZ, H, S, SDag, SqrtX, SqrtXDag, SqrtY, SqrtYDag, T, TDag, X, Y, Z,
};

/// Write one rule for each pair of one-qubit gates, and the list of those rules.
///
/// An entry `name: First::first, Second::second` cancels `First` followed by
/// `Second`. The op names are the snake-case struct names that `op!` needs.
macro_rules! one_qubit_pairs {
    ($($rule:ident: $first:ident::$a:ident, $second:ident::$b:ident;)+) => {
        $(
            #[rewrite_rule(language = Squin)]
            fn $rule() {
                let g = op![$first::$a(x)];
                let r = op![$second::$b(g)];
                rewrite!(r, {
                    replace!(r, x);
                })
            }
        )+

        fn one_qubit(stage: &mut Stage) -> Vec<PatternRule<Squin>> {
            vec![$($rule(stage)),+]
        }
    };
}

/// Write one rule for each two-qubit gate that is its own inverse, and the list of those rules.
macro_rules! two_qubit_pairs {
    ($($rule:ident: $gate:ident::$op:ident;)+) => {
        $(
            #[rewrite_rule(language = Squin)]
            fn $rule() {
                let (c1, t1) = op![$gate::$op(c, t)];
                let (c2, t2) = op![$gate::$op(c1, t1)];
                rewrite!(c2, {
                    replace!(c2, c);
                    replace!(t2, t);
                })
            }
        )+

        fn two_qubit(stage: &mut Stage) -> Vec<PatternRule<Squin>> {
            vec![$($rule(stage)),+]
        }
    };
}

one_qubit_pairs! {
    x_x: X::x, X::x;
    y_y: Y::y, Y::y;
    z_z: Z::z, Z::z;
    h_h: H::h, H::h;
    s_s_dag: S::s, SDag::s_dag;
    s_dag_s: SDag::s_dag, S::s;
    t_t_dag: T::t, TDag::t_dag;
    t_dag_t: TDag::t_dag, T::t;
    sqrt_x_sqrt_x_dag: SqrtX::sqrt_x, SqrtXDag::sqrt_x_dag;
    sqrt_x_dag_sqrt_x: SqrtXDag::sqrt_x_dag, SqrtX::sqrt_x;
    sqrt_y_sqrt_y_dag: SqrtY::sqrt_y, SqrtYDag::sqrt_y_dag;
    sqrt_y_dag_sqrt_y: SqrtYDag::sqrt_y_dag, SqrtY::sqrt_y;
}

two_qubit_pairs! {
    cx_cx: CX::c_x;
    cy_cy: CY::c_y;
    cz_cz: CZ::c_z;
}

/// Return every cancel rule.
pub(super) fn patterns(stage: &mut Stage) -> Vec<PatternRule<Squin>> {
    let mut patterns = one_qubit(stage);
    patterns.extend(two_qubit(stage));
    patterns
}
