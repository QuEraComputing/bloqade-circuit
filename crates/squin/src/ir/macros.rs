//! Generate the trait impls that repeat for each statement.

/// Implement a trait with its default methods for each listed type.
///
/// `plain!(Threads, for Alloc, Free);` writes `impl Threads for Alloc {}`
/// and the same line for `Free`. With `generic` before the trait, each impl
/// is generic over the type lattice, such as `impl<Ty> Threads for Alloc<Ty> {}`.
macro_rules! plain {
    (generic $trait:path, for $($statement:ident),+ $(,)?) => {
        $(impl<Ty: $crate::ir::types::QuantumTypes> $trait for $statement<Ty> {})+
    };
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
    (generic $wrapper:ident { $($variant:ident),+ $(,)? }) => {
        impl<Ty: $crate::ir::types::QuantumTypes> $crate::ir::traits::Threads for $wrapper<Ty> {
            fn threads(&self) -> $crate::ir::traits::Pairs {
                match self {
                    $(Self::$variant(inner) => inner.threads(),)+
                }
            }
        }
    };
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
