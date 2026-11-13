//! Give the measurement statements their forward rules.

use kirin_interpreter::dialect::{
    ForwardEval, Interpretable, SparseForwardEffect, SparseForwardInterp,
};

use crate::analysis::QuantumValue;
use crate::ir::dialects::measurement::{
    GetResult, IsLost, IsOne, IsZero, PackResults, ResultsLength,
};

/// Give the result of a measurement statement a value that the domain does not track.
///
/// A measurement outcome is known only when the program runs.
macro_rules! untracked {
    ($($statement:ty => $result:ident),+ $(,)?) => {$(
        impl<I> Interpretable<I, ForwardEval> for $statement
        where
            I: SparseForwardInterp,
            I::Value: QuantumValue,
        {
            fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
                interp.write(self.$result, I::Value::untracked())?;
                Ok(SparseForwardEffect::Next)
            }
        }
    )+};
}

untracked!(
    PackResults => packed,
    GetResult => result,
    ResultsLength => length,
    IsZero => answer,
    IsOne => answer,
    IsLost => answer,
);
