from kirin import interp

from bloqade.pyqrack.base import PyQrackInterpreter
from bloqade.decoders.dialects import annotate


@annotate.dialect.register(key="pyqrack")
class PyQrackAnnotateMethods(interp.MethodTable):
    """No-op handlers for the ``annotate`` dialect on the PyQrack simulator.

    ``annotate`` statements (detectors, observables) are decoder annotations
    that have no effect on state-vector simulation. Registering these handlers
    lets a kernel containing them run on PyQrack instead of raising
    ``Missing implementation``; the statements are simply ignored.
    """

    @interp.impl(annotate.stmts.SetDetector)
    def set_detector(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: annotate.stmts.SetDetector,
    ):
        return (None,)

    @interp.impl(annotate.stmts.SetObservable)
    def set_observable(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: annotate.stmts.SetObservable,
    ):
        return (None,)
