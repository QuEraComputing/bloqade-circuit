from kirin.analysis import ForwardFrame

from bloqade.analysis.address import Address


def collect_address_types(frame: ForwardFrame[Address], typ) -> list[Address]:
    return [
        address_type
        for address_type in frame.entries.values()
        if isinstance(address_type, typ)
    ]
