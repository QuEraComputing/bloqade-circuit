from kirin import interp
from kirin.dialects import py, ilist
from kirin.analysis.forward import ForwardFrame

from bloqade.analysis import address
from bloqade.decoders.dialects import annotate
from bloqade.squin.rewrite.wrap_analysis import AddressAttribute

from . import lattice
from .analysis import OutputAnalysis
from ...dialects import logical


@py.tuple.dialect.register(key="bloqade.gemini.analysis.output")
class TupleMethods(interp.MethodTable):
    @interp.impl(py.tuple.New)
    def new_tuple(
        self,
        interp_: OutputAnalysis,
        frame: ForwardFrame[lattice.Output],
        stmt: py.tuple.New,
    ):
        return (lattice.TupleResult(frame.get_values(stmt.args)),)


@ilist.dialect.register(key="bloqade.gemini.analysis.output")
class IListMethods(interp.MethodTable):
    @interp.impl(ilist.New)
    def new_ilist(
        self,
        interp_: OutputAnalysis,
        frame: ForwardFrame[lattice.Output],
        stmt: ilist.New,
    ):
        return (lattice.IListResult(tuple(frame.get_values(stmt.args))),)


@py.binop.dialect.register(key="bloqade.gemini.analysis.output")
class PyBinOpMethods(interp.MethodTable):
    @interp.impl(py.binop.Add)
    def add(
        self,
        interp_: OutputAnalysis,
        frame: ForwardFrame[lattice.Output],
        stmt: py.binop.Add,
    ):
        left = frame.get(stmt.left)
        right = frame.get(stmt.right)

        match (left, right):
            case (lattice.IListResult(lhs_data), lattice.IListResult(rhs_data)):
                return (lattice.IListResult(data=lhs_data + rhs_data),)
            case (lattice.TupleResult(lhs_data), lattice.TupleResult(rhs_data)):
                return (lattice.TupleResult(data=lhs_data + rhs_data),)
            case _:
                return (lattice.Output.bottom(),)


@py.indexing.dialect.register(key="bloqade.gemini.analysis.output")
class PyIndexingMethods(interp.MethodTable):
    @interp.impl(py.indexing.GetItem)
    def get_item(
        self,
        interp_: OutputAnalysis,
        frame: ForwardFrame[lattice.Output],
        stmt: py.indexing.GetItem,
    ):
        container = frame.get(stmt.container)
        index = interp_.expect_const(stmt.index, int)

        if isinstance(container, lattice.ImmutableContainerResult):
            try:
                return (container.data[index],)
            except IndexError:
                pass

        return (lattice.Output.bottom(),)


@logical.dialect.register(key="bloqade.gemini.analysis.output")
class LogicalMethods(interp.MethodTable):
    @interp.impl(logical.stmts.TerminalLogicalMeasurement)
    def terminal_logical_measurement(
        self,
        interp_: OutputAnalysis,
        frame: ForwardFrame[lattice.Output],
        stmt: logical.stmts.TerminalLogicalMeasurement,
    ):
        logical_reg = stmt.qubits.hints.get("address")
        if not isinstance(logical_reg, AddressAttribute):
            return (lattice.Output.bottom(),)

        logical_reg_address = logical_reg.address

        if not isinstance(logical_reg_address, address.AddressReg):
            return (lattice.Output.bottom(),)

        def logical_to_physical(logical_index: int):
            return lattice.IListResult(
                tuple(
                    map(
                        lattice.MeasurementResult,
                        range(
                            interp_.num_physical_qubits * logical_index,
                            interp_.num_physical_qubits * (logical_index + 1),
                        ),
                    )
                )
            )

        return (
            lattice.IListResult(
                tuple(map(logical_to_physical, logical_reg_address.data))
            ),
        )


@annotate.dialect.register(key="bloqade.gemini.analysis.output")
class AnnotateMethods(interp.MethodTable):

    @interp.impl(annotate.stmts.SetDetector)
    def set_detector(
        self,
        interp_: OutputAnalysis,
        frame: ForwardFrame[lattice.Output],
        stmt: annotate.stmts.SetDetector,
    ):
        detector_id = interp_.detector_count
        interp_.detector_count += 1
        return (lattice.DetectorResult(detector_id=detector_id),)

    @interp.impl(annotate.stmts.SetObservable)
    def set_observable(
        self,
        interp_: OutputAnalysis,
        frame: ForwardFrame[lattice.Output],
        stmt: annotate.stmts.SetObservable,
    ):
        return (
            lattice.ObservableResult(observable_id=interp_.expect_const(stmt.idx, int)),
        )
