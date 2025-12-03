from kirin import ir, interp as _interp
from kirin.analysis import ForwardFrame
from kirin.dialects import func

from bloqade import qubit, gemini
from bloqade.analysis.address.lattice import AddressReg, AddressQubit
from bloqade.analysis.measure_id.lattice import MeasureIdTuple

from .analysis import _GeminiTerminalMeasurementValidationAnalysis


@qubit.dialect.register(key="gemini.validate.terminal_measurement")
class __QubitGeminiMeasurementValidation(_interp.MethodTable):

    # This is a non-logical measurement, can safely flag as invalid
    @_interp.impl(qubit.stmts.Measure)
    def measure(
        self,
        interp: _GeminiTerminalMeasurementValidationAnalysis,
        frame: ForwardFrame,
        stmt: qubit.stmts.Measure,
    ):

        interp.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                "Non-terminal measurements are not allowed in Gemini programs!",
            ),
        )

        return (interp.lattice.bottom(),)


@gemini.logical.dialect.register(key="gemini.validate.terminal_measurement")
class __GeminiLogicalMeasurementValidation(_interp.MethodTable):

    # This is a logical terminal measurement, which is allowed
    # but we impose the following restrictions:
    # 1. All qubits spawned MUST be consumed
    @_interp.impl(gemini.logical.stmts.TerminalLogicalMeasurement)
    def terminal_measure(
        self,
        interp: _GeminiTerminalMeasurementValidationAnalysis,
        frame: ForwardFrame,
        stmt: gemini.logical.stmts.TerminalLogicalMeasurement,
    ):

        # should only be one terminal measurement EVER
        if not interp.terminal_measurement_encountered:
            interp.terminal_measurement_encountered = True
        else:
            interp.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "Multiple terminal measurements are not allowed in Gemini logical programs!",
                ),
            )
            return (interp.lattice.bottom(),)

        # If we confirm there isn't a duplicate terminal measurement,
        # now we need to check that for all the qubits that were spawned,
        # they are all consumed by this measurement
        address_analysis_results = interp.address_analysis_results
        measurement_analysis_results = interp.measurement_analysis_results

        # should just be one MeasureIDTuple
        measure_lattice_element = measurement_analysis_results.get_values(stmt.results)[
            0
        ]

        # Figure out the total number of qubits spawned, keeping in mind that if a user
        # "shuffles" the qubits (puts them in a new container, splits one off from a container type, etc.)
        # it should be accounted for. This would be much cleaner if there was a way to propagate the
        # final qubit count saved in the actual interpreter for address analysis...
        witnessed_qubits = set()
        total_qubits_allocated = 0
        for address_lattice_elem in address_analysis_results.entries.values():

            match address_lattice_elem:
                case AddressReg(data=data):
                    for data_elem in data:
                        if data_elem not in witnessed_qubits:
                            witnessed_qubits.add(data_elem)
                            total_qubits_allocated += 1
                case AddressQubit(data=data):
                    if data not in witnessed_qubits:
                        witnessed_qubits.add(data)
                        total_qubits_allocated += 1

        # could make these proper exceptions but would be tricky to communicate to user
        # without revealing under-the-hood details
        assert isinstance(measure_lattice_element, MeasureIdTuple)

        if len(measure_lattice_element.data) != total_qubits_allocated:
            interp.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "The number of qubits in the terminal measurement does not match the number of total qubits allocated! "
                    + f"{total_qubits_allocated} qubits were allocated but only {len(measure_lattice_element.data)} were measured.",
                ),
            )
            return (interp.lattice.bottom(),)

        return (interp.lattice.bottom(),)


@func.dialect.register(key="gemini.validate.terminal_measurement")
class Func(_interp.MethodTable):
    @_interp.impl(func.Invoke)
    def return_(
        self,
        interp: _GeminiTerminalMeasurementValidationAnalysis,
        frame: ForwardFrame,
        stmt: func.Invoke,
    ):
        _, ret = interp.call(
            stmt.callee.code,
            interp.method_self(stmt.callee),
            *frame.get_values(stmt.inputs),
        )

        return (ret,)
