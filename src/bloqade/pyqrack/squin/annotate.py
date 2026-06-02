from kirin import interp

from bloqade.decoders.dialects import annotate
from bloqade.pyqrack.base import PyQrackInterpreter


@annotate.dialect.register(key="pyqrack")
class PyQrackAnnotateMethods(interp.MethodTable):
    @interp.impl(annotate.stmts.SetDetector)
    @interp.impl(annotate.stmts.SetObservable)
    def ignore_annotation(
        self,
        interp_: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: annotate.stmts.SetDetector | annotate.stmts.SetObservable,
    ):
        return (None,)
