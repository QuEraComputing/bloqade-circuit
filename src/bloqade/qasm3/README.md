# bloqade QASM3 Module

The `bloqade.qasm3` module provides an [OpenQASM 3.0](https://openqasm.com/) frontend
for bloqade-circuit. You can write quantum programs using Python decorators or parse
OpenQASM 3.0 source strings/files, then convert them to the squin IR for further
compilation and execution.

## Getting Started

### Writing programs with Python decorators

Define custom gates with `@qasm3.gate` and main programs with `@qasm3.main`:

```python
from bloqade import qasm3
from bloqade.squin.passes import QASM3ToSquin
from bloqade.qasm3.emit import QASM3Emitter

# Define a custom gate
@qasm3.gate
def bell(a: qasm3.Qubit, b: qasm3.Qubit):
    qasm3.h(a)
    qasm3.cx(a, b)

# Define the main program
@qasm3.main
def prog():
    q = qasm3.qreg(2)
    c = qasm3.bitreg(2)
    qasm3.h(q[1])
    bell(q[0], q[1])
    qasm3.measure(q[0], c[0])
    qasm3.measure(q[1], c[1])

# Verify the IR
prog.verify()
```

### Emitting OpenQASM 3.0 source

```python
qasm_source = QASM3Emitter().emit(prog)
print(qasm_source)
```

Output:

```
OPENQASM 3.0;
include "stdgates.inc";

gate bell a, b {
  h a;
  cx a, b;
}

qubit[2] q;
bit[2] c;
h q[1];
bell q[0], q[1];
c[0] = measure q[0];
c[1] = measure q[1];
```

### Parsing OpenQASM 3.0 source strings

```python
source = """
OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
c[0] = measure q[0];
c[1] = measure q[1];
"""
mt = qasm3.loads(source)
mt.verify()
```

### Loading from a file

```python
mt = qasm3.loadfile("my_circuit.qasm")
mt.verify()
```

### Converting QASM3 IR to squin

```python
QASM3ToSquin(dialects=prog.dialects)(prog)
prog.verify()
prog.print()
```

### Available gate and operation wrappers

Single-qubit gates: `qasm3.h`, `qasm3.x`, `qasm3.y`, `qasm3.z`, `qasm3.s`, `qasm3.t`

Rotation gates: `qasm3.rx`, `qasm3.ry`, `qasm3.rz`

Two-qubit gates: `qasm3.cx`, `qasm3.cy`, `qasm3.cz`

General unitary: `qasm3.u(qubit, theta, phi, lam)`

Operations: `qasm3.measure`, `qasm3.reset`, `qasm3.barrier`

Registers: `qasm3.qreg(n)`, `qasm3.bitreg(n)`

Constants: `qasm3.pi()`

---

## OpenQASM 3.0 Feature Support

This section tracks which [OpenQASM 3.0](https://openqasm.com/) language features
are supported by this module and which are not yet implemented.

Legend: ✅ Supported | ❌ Not yet implemented

### Quantum Types & Declarations

| Feature | Status | Notes |
|---------|--------|-------|
| `qubit q;` | ✅ | Single qubit declaration |
| `qubit[N] q;` | ✅ | Qubit register declaration |
| `bit c;` | ✅ | Single bit declaration |
| `bit[N] c;` | ✅ | Bit register declaration |
| `int[N]` / `uint[N]` | ✅ | Width erased to generic int |
| `float[N]` | ✅ | Width erased to generic float |
| `bool` | ✅ | Boolean type |
| `complex[float[N]]` | ✅ | Width erased to generic complex |
| `angle[N]` | ❌ | |
| `duration` | ❌ | |
| `stretch` | ❌ | |
| `const` declarations | ❌ | |
| `array` types | ❌ | |
| Physical qubits (`$0`) | ❌ | |
| Register aliasing (`let`) | ❌ | |

### Gates

| Feature | Status | Notes |
|---------|--------|-------|
| `h`, `x`, `y`, `z`, `s`, `t` | ✅ | Single-qubit gates |
| `cx`, `cy`, `cz` | ✅ | Two-qubit controlled gates |
| `rx`, `ry`, `rz` | ✅ | Rotation gates |
| `U` / `u3` | ✅ | General unitary |
| Custom gate definitions | ✅ | `gate name(...) q { ... }` |
| Parameterized custom gates | ✅ | Classical angle parameters |
| Gate composition | ✅ | Gates calling other gates |
| Gate modifiers (`ctrl @`, `inv @`, `pow(k) @`) | ❌ | |

### Quantum Operations

| Feature | Status | Notes |
|---------|--------|-------|
| `measure` | ✅ | `c[0] = measure q[0];` |
| `reset` | ✅ | |
| `barrier` | ✅ | Single and multi-qubit |
| Simple qubit indexing (`q[i]`) | ✅ | |
| Multi-dimensional indexing | ❌ | |

### Classical Types & Expressions

| Feature | Status | Notes |
|---------|--------|-------|
| Integer literals | ✅ | |
| Float literals | ✅ | |
| Boolean literals | ✅ | `true` / `false` |
| Imaginary literals | ✅ | e.g. `1.5im` |
| `pi` constant | ✅ | |
| `tau`, `euler` constants | ❌ | |
| `+`, `-`, `*`, `/` | ✅ | Arithmetic operators |
| `**` (power) | ✅ | |
| `%` (modulo) | ✅ | |
| Unary `-` (negation) | ✅ | |
| `~` (bitwise NOT) | ✅ | |
| `<<`, `>>` (bit shift) | ❌ | |
| `&`, `\|`, `^` (bitwise AND/OR/XOR) | ❌ | |
| `==`, `!=`, `<`, `>`, `<=`, `>=` | ❌ | Comparison operators |
| `&&`, `\|\|`, `!` | ❌ | Logical operators |
| Ternary `? :` | ❌ | |
| Type casting | ❌ | |
| Concatenation expressions | ❌ | |

### Math Functions

| Feature | Status | Notes |
|---------|--------|-------|
| `sin`, `cos`, `tan` | ✅ | |
| `exp`, `log`, `sqrt` | ✅ | |
| `arcsin`, `arccos`, `arctan` | ❌ | |
| `ceiling`, `floor` | ❌ | |
| `mod` (function form) | ❌ | Operator `%` is supported |
| `popcount`, `rotl`, `rotr` | ❌ | |

### Control Flow

| Feature | Status | Notes |
|---------|--------|-------|
| `for` loops | ❌ | |
| `while` loops | ❌ | |
| `if` / `else` | ❌ | |
| `switch` | ❌ | |
| `break` / `continue` | ❌ | |

### Subroutines

| Feature | Status | Notes |
|---------|--------|-------|
| `def` subroutines | ❌ | Gate definitions *are* supported |
| `return` in subroutines | ❌ | |
| `extern` declarations | ❌ | |

### Includes

| Feature | Status | Notes |
|---------|--------|-------|
| `include "stdgates.inc";` | ✅ | |
| Arbitrary file includes | ❌ | |

### Timing & Pulses

| Feature | Status | Notes |
|---------|--------|-------|
| `delay` | ❌ | |
| `box` | ❌ | |
| Pulse-level definitions (`defcal`) | ❌ | |

### Directives & Metadata

| Feature | Status | Notes |
|---------|--------|-------|
| `pragma` | ❌ | Vendor-specific directives |
| Annotations (`@annotation`) | ❌ | |

### I/O

| Feature | Status | Notes |
|---------|--------|-------|
| `input` / `output` declarations | ❌ | |
