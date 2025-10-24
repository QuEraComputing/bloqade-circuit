OPENQASM 2.0;
include "qelib1.inc";
gate custom_gate a, b {
  CX a, b;
}
qreg qreg[4];
creg creg[2];
CX qreg[0], qreg[1];
reset qreg[0];
measure qreg[0] -> creg[0];
if (creg[0] == 1) reset qreg[1];
custom_gate qreg[0], qreg[1];
custom_gate qreg[1], qreg[2];
