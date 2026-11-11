//! Describe the structure of the measurement-result statements.

use super::{Lending, Nesting, Offset, Structure};
use crate::ir::macros::plain;
use crate::ir::ops::{BitsGet, BitsLength, BitsOp, BitsPack};

delegate!(BitsOp { Pack, Get, Length });
plain!(Structure, for BitsPack, BitsGet, BitsLength);
