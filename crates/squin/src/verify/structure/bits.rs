//! Describe the structure of the measurement-result statements.

use super::{Lending, Nesting, Offset, Place, Structure};
use crate::ir::dialects::bits::{BitsGet, BitsLength, BitsOp, BitsPack};

delegate!(BitsOp { Pack, Get, Length });
placed!(Anywhere, for BitsPack, BitsGet, BitsLength);
