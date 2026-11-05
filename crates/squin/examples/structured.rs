use kirin::prelude::*;
use kirin_function::Return;
use kirin_scf::StructuredControlFlow;
use squin::{Squin, Type, ops::IntConstant};

#[derive(
    Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, serde::Serialize, serde::Deserialize,
)]
#[kirin(builders, type = Type)]
#[chumsky(format = "fn {:name}{sig} {body}")]
pub struct Function {
    #[kirin(callable_body)]
    pub body: Block,
    pub sig: Signature<Type>,
}

#[derive(
    Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, serde::Serialize, serde::Deserialize,
)]
#[kirin(builders, type = Type)]
pub enum StructuredCircuit {
    #[wraps]
    Squin(Squin),
    #[wraps]
    Scf(StructuredControlFlow<Type>),
    #[wraps]
    Constant(IntConstant),
    #[wraps]
    Function(Function),
    #[wraps]
    GraphFunction(squin::ops::Function),
    #[wraps]
    Return(Return<Type>),
}

#[derive(Debug, StageMeta, ParseDispatch, RenderDispatch, serde::Serialize, serde::Deserialize)]
pub enum StructuredStage {
    #[stage(name = "structured")]
    Structured(StageInfo<StructuredCircuit>),
}

#[cfg(not(test))]
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let source = match std::env::args_os().nth(1) {
        Some(path) => std::fs::read_to_string(path)?,
        None => include_str!("structured.kirin").to_owned(),
    };
    let mut pipeline = Pipeline::<StructuredStage>::new();
    pipeline.parse(&source)?;
    for StructuredStage::Structured(stage) in pipeline.stages() {
        verify_derived(stage)?;
    }
    println!("{}", pipeline.sprint());
    Ok(())
}
