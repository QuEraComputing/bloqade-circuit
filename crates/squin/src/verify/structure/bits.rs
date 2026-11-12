//! Describe the structure of the measurement-result statements.

use super::{Lending, Nesting, Offset, Structure};
use crate::ir::dialects::bits::{BitsGet, BitsLength, BitsOp, BitsPack};
use crate::ir::macros::plain;

delegate!(BitsOp { Pack, Get, Length });
plain!(Structure, for BitsPack, BitsGet, BitsLength);
