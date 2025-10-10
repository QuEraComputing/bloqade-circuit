from kirin.passes.inline import InlinePass

from bloqade import squin


def test_stuff():

    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])

    main.print()
    InlinePass(dialects=main.dialects).fixpoint(main)
    main.print()


test_stuff()
