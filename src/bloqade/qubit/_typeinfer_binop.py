"""Type inference overlay for BitXor on MeasurementResult."""

from kirin import interp
from kirin.dialects import py
from kirin.dialects.py.binop.typeinfer import TypeInfer

from bloqade.types import MeasurementResultType


@interp.impl(py.BitXor, MeasurementResultType, MeasurementResultType)
def bitxor_measurement(self, interp_, frame, stmt):
    return (MeasurementResultType,)


TypeInfer.bitxor_measurement = bitxor_measurement
