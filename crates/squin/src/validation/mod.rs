use crate::{RegisterLength, Type};
use kirin::prelude::*;
use kirin_interpreter::{
    Callee, ForwardEval, InterpDispatch, Interpretable, InterpreterError, SparseForwardEffect,
    SparseForwardInterp, SparseForwardInterpreter, SparseForwardTransfer,
};
use std::collections::BTreeSet;
use std::fmt;

mod rules;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ValidationError {
    pub statement: Option<Statement>,
    pub message: String,
}

impl ValidationError {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            statement: None,
            message: message.into(),
        }
    }
}

impl fmt::Display for ValidationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if let Some(statement) = self.statement {
            write!(f, "At {statement:?}: ")?;
        }
        f.write_str(&self.message)
    }
}

impl std::error::Error for ValidationError {}

impl From<InterpreterError> for ValidationError {
    fn from(error: InterpreterError) -> Self {
        Self::new(format!("Kirin could not analyze the circuit: {error}"))
    }
}

impl From<std::convert::Infallible> for ValidationError {
    fn from(error: std::convert::Infallible) -> Self {
        match error {}
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Value {
    Bottom,
    Top,
    Scalar(Type),
    Int(Option<i64>),
    Register {
        declared: Option<Type>,
        length: Option<u64>,
        empty: BTreeSet<u64>,
    },
}

impl Value {
    fn parameter(ty: Type) -> Self {
        match ty {
            Type::Int => Self::Int(None),
            Type::Register { length } => Self::Register {
                declared: Some(ty),
                length: match length {
                    RegisterLength::Known { length } => Some(length),
                    RegisterLength::Dynamic => None,
                },
                empty: BTreeSet::new(),
            },
            _ => Self::Scalar(ty),
        }
    }

    fn expect_type(&mut self, actual: Type) -> Result<(), ValidationError> {
        let required = match self {
            Self::Scalar(ty) => *ty,
            Self::Int(_) => Type::Int,
            Self::Register {
                declared, length, ..
            } => {
                if let Some(ty) = declared {
                    *ty
                } else {
                    if actual != Type::dynamic_register()
                        && Some(actual) != length.map(Type::register)
                    {
                        return Err(ValidationError::new(
                            "The allocation result must have a register type that matches its size.",
                        ));
                    }
                    *declared = Some(actual);
                    actual
                }
            }
            _ => {
                return Err(ValidationError::new(
                    "The checker requires a proven value type.",
                ));
            }
        };
        if actual != required {
            return Err(ValidationError::new(format!(
                "The value has type {actual}. This operation requires {required}."
            )));
        }
        Ok(())
    }

    fn full(&self) -> Result<(), ValidationError> {
        match self {
            Self::Register { empty, .. } if empty.is_empty() => Ok(()),
            Self::Register { .. } => Err(ValidationError::new(
                "The register has empty slots. Release wires before disposal or return.",
            )),
            _ => Err(ValidationError::new("The operation requires a register.")),
        }
    }
}

impl From<i64> for Value {
    fn from(value: i64) -> Self {
        Self::Int(Some(value))
    }
}

impl Lattice for Value {
    fn join(&self, other: &Self) -> Self {
        match (self, other) {
            (Self::Bottom, _) => other.clone(),
            (_, Self::Bottom) => self.clone(),
            _ if self == other => self.clone(),
            _ => Self::Top,
        }
    }
    fn meet(&self, other: &Self) -> Self {
        match (self, other) {
            (Self::Top, _) => other.clone(),
            (_, Self::Top) => self.clone(),
            _ if self == other => self.clone(),
            _ => Self::Bottom,
        }
    }
    fn is_subseteq(&self, other: &Self) -> bool {
        self.join(other) == *other
    }
}

impl HasBottom for Value {
    fn bottom() -> Self {
        Self::Bottom
    }
}

impl Widen for Value {
    fn widen(&self, other: &Self) -> Self {
        self.join(other)
    }
}

#[derive(StageMeta)]
pub enum ValidationStage<L: Dialect<Type = Type>> {
    #[stage(name = "validation")]
    Circuit(StageInfo<L>),
}

impl<L, I> InterpDispatch<I> for ValidationStage<L>
where
    L: Dialect<Type = Type> + Interpretable<I, ForwardEval>,
    I: SparseForwardInterp<Value = Value, Error = ValidationError>,
{
    fn dispatch_statement(
        &self,
        statement: Statement,
        interp: &mut I,
    ) -> Result<I::Effect, I::Error> {
        let Self::Circuit(stage) = self;
        let op = statement.definition(stage);
        let result = (|| {
            let effect = op.interpret(interp)?;
            if !matches!(effect, SparseForwardEffect::Next) {
                return Err(ValidationError::new(
                    "The checker rejects control flow and function calls.",
                ));
            }
            for &result in op.results() {
                let mut value = interp.read(result)?;
                value.expect_type(*result.expect_info(stage).ty())?;
                interp.write(result, value)?;
            }
            Ok(effect)
        })();
        result.map_err(|mut error: ValidationError| {
            error.statement = Some(statement);
            error
        })
    }
}

pub fn validate<L>(stage: &StageInfo<L>) -> Result<(), ValidationError>
where
    L: Dialect<Type = Type> + HasCallableBody + HasSignature<L>,
    for<'ir> L: Interpretable<
            SparseForwardTransfer<'ir, ValidationStage<L>, Value, ValidationError>,
            ForwardEval,
        >,
{
    verify_derived(stage)
        .map_err(|e| ValidationError::new(format!("Kirin rejected the structure: {e}")))?;
    check_structure(stage)?;
    let mut builder = BuilderStageInfo::from(stage.clone());
    let mut functions = Vec::new();
    for item in stage.statement_arena().iter() {
        let op = item.definition();
        let Some(Body::DiGraph(graph)) = op.callable_body() else {
            continue;
        };
        let signature = op
            .signature()
            .ok_or_else(|| ValidationError::new("The function requires a signature."))?;
        let node: &LinkedListNode<Statement> = (&**item).into();
        let staged = builder
            .staged_function()
            .signature(signature.clone())
            .new()
            .map_err(|e| ValidationError::new(e.to_string()))?;
        let specialized = builder
            .specialize()
            .staged_func(staged)
            .definition(node.ptr)
            .new()
            .map_err(|e| ValidationError::new(e.to_string()))?;
        functions.push((specialized, graph, signature));
    }
    let mut pipeline = Pipeline::new();
    let stage_id = pipeline.add_stage_raw(ValidationStage::Circuit(
        builder
            .finalize()
            .map_err(|e| ValidationError::new(e.to_string()))?,
    ));
    for (function, graph, signature) in functions {
        let arguments = signature.params().iter().copied().map(Value::parameter);
        let (returned, _) = SparseForwardInterpreter::<_, Value, ValidationError>::new(&pipeline)
            .analyze(stage_id, Callee::Specialized(function), arguments)?;
        let body = graph.expect_info(stage);
        if returned.len() != body.yields().len() {
            return Err(ValidationError::new(
                "The analysis must produce every graph yield.",
            ));
        }
        for mut value in returned {
            value.expect_type(*signature.ret())?;
            if matches!(value, Value::Register { .. }) {
                value.full()?;
            }
        }
    }
    Ok(())
}

fn check_structure<L>(stage: &StageInfo<L>) -> Result<(), ValidationError>
where
    L: Dialect<Type = Type> + HasCallableBody + HasSignature<L>,
{
    if stage.block_arena().iter().next().is_some()
        || stage.cfg_arena().iter().next().is_some()
        || stage.ungraph_arena().iter().next().is_some()
    {
        return Err(ValidationError::new(
            "The checker supports directed graph bodies and rejects control flow.",
        ));
    }
    for item in stage.ssa_arena().iter() {
        let Some(info) = item.as_ref() else {
            continue;
        };
        let owner = match *info.kind() {
            SSAKind::Port(PortParent::DiGraph(graph), index)
                if graph
                    .expect_info(stage)
                    .ports()
                    .get(index)
                    .copied()
                    .map(SSAValue::from)
                    == Some(info.id()) =>
            {
                graph
            }
            SSAKind::Result(stmt, index)
                if stmt
                    .definition(stage)
                    .results()
                    .nth(index)
                    .copied()
                    .map(SSAValue::from)
                    == Some(info.id()) =>
            {
                let Some(StatementParent::DiGraph(graph)) = *stmt.parent(stage) else {
                    return Err(ValidationError::new(
                        "Every value must have a definition in a function.",
                    ));
                };
                graph
            }
            _ => {
                return Err(ValidationError::new(
                    "Every value must identify its defining operation or graph port.",
                ));
            }
        };
        for usage in info.uses() {
            let local = match usage {
                Use::StatementOperand { stmt, .. } => {
                    *stmt.parent(stage) == Some(StatementParent::DiGraph(owner))
                }
                Use::DiGraphYield { graph, .. } => *graph == owner,
            };
            if !local {
                return Err(ValidationError::new(format!(
                    "Value {} has a use outside its defining graph.",
                    info.id()
                )));
            }
        }
        if info.ty().is_linear() && info.uses().len() != 1 {
            let count = info.uses().len();
            let uses = if count == 0 { "0" } else { "multiple" };
            return Err(ValidationError::new(format!(
                "Linear value {} has {uses} consuming uses ({count}). It requires exactly one.",
                info.id()
            )));
        }
        if let Type::Register {
            length: RegisterLength::Known { length },
        } = info.ty()
        {
            if *length > i64::MAX as u64 {
                return Err(ValidationError::new(
                    "The register length must fit Int, whose maximum is 9223372036854775807.",
                ));
            }
        }
    }
    for item in stage.statement_arena().iter() {
        let op = item.definition();
        let node: &LinkedListNode<Statement> = (&**item).into();
        match *node.ptr.parent(stage) {
            None if matches!(op.callable_body(), Some(Body::DiGraph(_))) => {
                let Some(Body::DiGraph(graph)) = op.callable_body() else {
                    unreachable!()
                };
                if graph.get_info(stage).and_then(|body| body.parent()) != Some(node.ptr) {
                    return Err(ValidationError::new(
                        "Each function must own a separate graph body.",
                    ));
                }
            }
            Some(StatementParent::DiGraph(_))
                if op.callable_body().is_none()
                    && op.digraphs().next().is_none()
                    && op.cfgs().next().is_none()
                    && op.blocks().next().is_none()
                    && op.ungraphs().next().is_none()
                    && op.successors().next().is_none() => {}
            _ => {
                return Err(ValidationError::new(
                    "The checker does not support nested bodies, branches, or loops.",
                ));
            }
        }
    }
    for body in stage.digraph_arena().iter() {
        let parent = body
            .parent()
            .ok_or_else(|| ValidationError::new("Every graph requires an owning function."))?;
        let op = parent.definition(stage);
        if op.callable_body() != Some(Body::DiGraph(body.id())) {
            return Err(ValidationError::new("The function must own its graph."));
        }
        if body.edge_count() != body.ports().len() {
            return Err(ValidationError::new(
                "The checker does not support graph captures.",
            ));
        }
        let sig = op
            .signature()
            .ok_or_else(|| ValidationError::new("The function requires a signature."))?;
        if body.ports().len() != sig.params().len() {
            return Err(ValidationError::new(
                "The function signature and parameter count differ.",
            ));
        }
        for (&port, &ty) in body.ports().iter().zip(sig.params()) {
            Value::parameter(ty).expect_type(*port.expect_info(stage).ty())?;
        }
        if body.yields().len() != usize::from(*sig.ret() != Type::Unit) {
            return Err(ValidationError::new(
                "The graph yield count must match the function return type.",
            ));
        }
        for &value in body.yields() {
            Value::parameter(*sig.ret()).expect_type(*value.expect_info(stage).ty())?;
        }
    }
    for function in stage.staged_function_arena().iter() {
        for specialized in function.specializations() {
            if specialized
                .definition()
                .definition(stage)
                .signature()
                .as_ref()
                != Some(specialized.signature())
            {
                return Err(ValidationError::new(
                    "The specialization signature must match its function definition.",
                ));
            }
        }
    }
    Ok(())
}
