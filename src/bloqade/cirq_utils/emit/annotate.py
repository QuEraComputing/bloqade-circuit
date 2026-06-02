from kirin.interp import MethodTable, impl

from bloqade.decoders.dialects import annotate

from .base import EmitCirq, EmitCirqFrame


@annotate.dialect.register(key="emit.cirq")
class EmitCirqAnnotateMethods(MethodTable):
    @impl(annotate.stmts.SetDetector)
    @impl(annotate.stmts.SetObservable)
    def ignore_annotation(
        self,
        emit: EmitCirq,
        frame: EmitCirqFrame,
        stmt: annotate.stmts.SetDetector | annotate.stmts.SetObservable,
    ):
        return (emit.void,)
