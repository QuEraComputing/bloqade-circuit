from typing import TypeVar

from kirin.analysis import ForwardFrame

from bloqade.analysis.address import Address

T = TypeVar("T", bound=Address)


def collect_address_types(frame: ForwardFrame[Address], typ: type[T]) -> list[T]:
    return [
        address_type
        for address_type in frame.entries.values()
        if isinstance(address_type, typ)
    ]
