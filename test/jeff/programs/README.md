# Programs from the jeff project

The example programs and verifier fixtures of the
[jeff](https://github.com/unitaryfoundation/jeff) repository, copied
unchanged from its `examples/` and `tools/verifier/tests/` folders; the
files its verifier rejects are under `rejected/`.
They were produced by other compilers (Catalyst, TKET, a C++ translation) and
exercise spellings this conversion never emits itself: custom gate names,
arrays filled by index, one-bit constants in arithmetic. `test/jeff/test_programs.py`
states what each one does.

jeff is released under the Apache License, Version 2.0.
