"""Run each wire example in a separate process."""

import sys
import subprocess
from pathlib import Path

if __name__ == "__main__":
    for script in sorted(Path(__file__).parent.glob("[0-9][0-9]_*.py")):
        print(f"\n{script.name}", flush=True)
        subprocess.run([sys.executable, str(script)], check=True)
