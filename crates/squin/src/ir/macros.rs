//! Generate the trait impls that repeat for each statement.

/// Implement a trait with its default methods for each listed type.
///
/// `plain!(Threads, for Alloc, Free);` writes `impl Threads for Alloc {}`
/// and the same line for `Free`.
macro_rules! plain {
    ($trait:path, for $($statement:ty),+ $(,)?) => {
        $(impl $trait for $statement {})+
    };
}

/// Implement `Threads` for an enum that wraps one statement in each variant.
///
/// The method forwards to the statement of the variant. For example,
/// `delegate!(QubitOp { Alloc, Free });` makes `QubitOp::Alloc(inner).threads()`
/// return `inner.threads()`.
macro_rules! delegate {
    ($wrapper:ty { $($variant:ident),+ $(,)? }) => {
        impl $crate::ir::traits::Threads for $wrapper {
            fn threads(&self) -> $crate::ir::traits::Pairs {
                match self {
                    $(Self::$variant(inner) => inner.threads(),)+
                }
            }
        }
    };
}

pub(crate) use {delegate, plain};
