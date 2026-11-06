# Wire examples

Run all examples from the repository root:

```sh
uv run --locked python examples/wire/run_all.py
```

You can run each numbered script with the same command prefix.

| Script | Example |
| --- | --- |
| [01_indices.py](01_indices.py) | Print symbolic qubit indices inside a loop that prepares Bell pairs. |
| [02_dialects.py](02_dialects.py) | Show state, gate and noise operations for a noisy Bell pair. |
| [03_validation.py](03_validation.py) | Validate a three-qubit entangled state preparation. |
| [04_conversion.py](04_conversion.py) | Convert function calls, loops and branches to wire form and back. |
| [05_jeff.py](05_jeff.py) | Write and reload a Bell circuit through a temporary Jeff file. |
| [06_optimizations.py](06_optimizations.py) | Print a rotation circuit before and after the optional passes. |
| [07_direct_lowering.py](07_direct_lowering.py) | Lower a Bell-pair loop directly through Kirin’s Python lowering interface. |

Open [slides.html](slides.html) in a browser for the pass walkthrough.
