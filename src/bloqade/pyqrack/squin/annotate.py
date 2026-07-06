from kirin import interp

from bloqade.pyqrack.base import PyQrackInterpreter
from bloqade.decoders.dialects import annotate


@annotate.dialect.register(key="pyqrack")
class PyQrackAnnotateMethods(interp.MethodTable):
    @interp.impl(annotate.stmts.SetDetector)
    @interp.impl(annotate.stmts.SetObservable)
    def ignore_annotation(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: annotate.stmts.SetDetector | annotate.stmts.SetObservable,
    ):
        return tuple(None for _ in stmt.results)
