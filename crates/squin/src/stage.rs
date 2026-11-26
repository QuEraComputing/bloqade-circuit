use crate::Circuit;
use kirin::prelude::*;

#[derive(Debug, StageMeta, ParseDispatch, RenderDispatch, serde::Serialize, serde::Deserialize)]
pub enum Stage {
    #[stage(name = "squin")]
    Squin(StageInfo<Circuit>),
}
