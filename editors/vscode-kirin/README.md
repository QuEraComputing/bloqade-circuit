# Kirin IR syntax for VS Code

This extension highlights Kirin IR text, such as the squin kernels in `.kirin` files. It also highlights Markdown code blocks that start with `` ```kirin ``.

## What it colors

| Token | Example | Scope |
|---|---|---|
| SSA value | `%a0` | `variable.other.ssa` |
| Block | `^entry` | `entity.name.label.block` |
| Symbol | `@kernel` | `entity.name.function.symbol` |
| Attribute | `#pure` | `entity.other.attribute-name` |
| Structure keyword | `stage`, `specialize`, `digraph`, `capture` | `keyword.other.structure` |
| Control keyword | `ret`, `yield`, `conditional`, `repeat`, `circuit` | `keyword.control` |
| Gate | `h`, `cx`, `rz` | `support.function.gate` |
| Qubit statement | `alloc`, `measure`, `borrow`, `is_one` | `support.function.quantum` |
| Classical statement | `constant`, `add`, `lt`, `xor` | `keyword.operator.word` |
| Type | `Wire`, `MeasurementResult`, `i64` | `storage.type` |
| Number | `0.25`, `0x1F` | `constant.numeric` |
| Comment | `// note`, `/* note */` | `comment` |

The token rules follow the Kirin lexer in `kirin-lexer`. The keywords come from the `format` strings of the Kirin dialects and the squin dialects. If a dialect adds a statement, add its name to the matching list in `syntaxes/kirin.tmLanguage.json`.

## Install

1. In VS Code, open the command palette.
2. Run "Developer: Install Extension from Location...".
3. Select this folder, `editors/vscode-kirin`.
4. Open a `.kirin` file. The language mode in the status bar reads "Kirin".

VS Code copies the folder when it installs the extension. After you change the grammar, install it again and run "Developer: Reload Window".
