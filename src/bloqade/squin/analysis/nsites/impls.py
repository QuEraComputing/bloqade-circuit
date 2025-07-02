from kirin.dialects import scf, func
from kirin.dialects.scf.typeinfer import TypeInfer as ScfTypeInfer
from kirin.dialects.func.typeinfer import TypeInfer as FuncTypeInfer


@scf.dialect.register(key="op.nsites")
class ScfSquinOp(ScfTypeInfer):
    pass


@func.dialect.register(key="op.nsites")
class FuncSquinOp(FuncTypeInfer):
    pass
