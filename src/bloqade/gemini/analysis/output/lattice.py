from typing import final
from dataclasses import dataclass

from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)


@dataclass
class Output(
    SimpleJoinMixin["Output"],
    SimpleMeetMixin["Output"],
    BoundedLattice["Output"],
):

    @classmethod
    def bottom(cls) -> "Output":
        return Bottom()

    @classmethod
    def top(cls) -> "Output":
        return Unknown()


@final
class Bottom(Output, metaclass=SingletonMeta):
    """Error during interpretation or not part of the analysis."""

    def is_subseteq(self, other: Output) -> bool:
        return True


@final
class Unknown(Output, metaclass=SingletonMeta):
    """Can't determine if what the value is."""

    def is_subseteq(self, other: Output) -> bool:
        return isinstance(other, Unknown)


class ConcreteValue(Output):
    """Base class of concrete lattice elements. e. g. values with known qubit ids."""

    def is_subseteq(self, other: Output) -> bool:
        return self == other


@final
@dataclass
class MeasurementResult(ConcreteValue):
    """Measurement result output."""

    qubit_id: int


@final
@dataclass
class DetectorResult(ConcreteValue):
    """Detector result output."""

    detector_id: int


@final
@dataclass
class ObservableResult(ConcreteValue):
    """Observable result output."""

    observable_id: int


@dataclass
class ImmutableContainerResult(Output):
    """Class representing an immutable container of outputs."""

    data: tuple[Output, ...]

    def is_subseteq(self, other: Output) -> bool:
        return (
            isinstance(other, type(self))
            and len(self.data) == len(other.data)
            and all(s.is_subseteq(o) for s, o in zip(self.data, other.data))
        )

    def join(self, other: Output):
        if not isinstance(other, my_type := type(self)) or len(self.data) != len(
            other.data
        ):
            return super().join(other)

        return my_type(data=tuple(s.join(o) for s, o in zip(self.data, other.data)))

    def meet(self, other: Output):
        if not isinstance(other, my_type := type(self)) or len(self.data) != len(
            other.data
        ):
            return super().meet(other)

        return my_type(data=tuple(s.meet(o) for s, o in zip(self.data, other.data)))


@final
@dataclass
class IListResult(ImmutableContainerResult):
    """Immutable list of outputs."""

    pass


@final
@dataclass
class TupleResult(ImmutableContainerResult):
    """tuple of outputs."""

    pass
