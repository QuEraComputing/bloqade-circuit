//! Give the bits statements their forward rules.

use kirin_interpreter::dialect::{
    ForwardEval, Interpretable, SparseForwardEffect, SparseForwardInterp,
};

use super::forward;
use crate::analysis::QuantumValue;
use crate::ir::ops::{BitsGet, BitsLength, BitsOp, BitsPack};

forward!(BitsOp {
    Pack: BitsPack,
    Get: BitsGet,
    Length: BitsLength,
});

/// Give the result of a bits statement a value that the domain does not track.
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

untracked!(BitsPack => result, BitsGet => bit, BitsLength => length);
