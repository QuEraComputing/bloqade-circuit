from kirin.dialects import debug

from bloqade import stim

from .base import codegen


def test_debug():

    @stim.main
    def test_debug_main():
        debug.info("debug message")

    test_debug_main.print()
    out = codegen(test_debug_main)
    assert out.strip() == "# debug message"
