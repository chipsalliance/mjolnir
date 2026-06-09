# OpenTitan Earlgrey Threat Model

## Summary

This folder contains the offline threat model generated for the **OpenTitan Earlgrey** architecture.

It is created by digesting the open-source hardware specifications, SystemVerilog RTL, and C/C++ firmware using Gemini 3.1 Pro. The `PROMPT.md` file defines the adversarial persona and is used to synthesize the master `THREAT_MODEL.md` file.

This generated threat model is consumed during the Nix-based vulnerability scanning jobs. By loading this document as background context (`contextFile`), the auditing agent understands OpenTitan's specific hardware/software boundaries, hardening mechanisms, and system architecture _before_ looking for specific vulnerabilities.

## Creating the PROMPT.md

The `PROMPT.md` file was specifically tailored to evaluate the OpenTitan environment, focusing the AI on its unique architectural paradigms:

- The Hardware/Software boundary and proper usage of `SecMMIO` macros for fault injection resistance.
- Logic flaws and memory safety issues in the ROM and ROM_EXT execution phases.
- Lifecycle Controller (LC) states (TEST, DEV, PROD, RMA) and their interaction with debug interfaces (JTAG/RV_DM).
- The Ibex RISC-V core, TileLink bus matrix interactions, and SystemVerilog RTL state machines.
- Device Interface Functions (DIFs) and cryptographic boundaries (e.g., Keymgr, OTBN).

## Harness

The generation is performed using the `run_threat_model.sh` harness. Because OpenTitan is a massive, fully open-source project, this script completely automates the ingestion process. It removes the need for a static file list, ensuring the threat model is always built against a pristine code state.

### Automated Ingestion

Instead of manually tracking files, the script performs the following:

1. **Repository Cloning:** Clones `https://github.com/lowRISC/opentitan.git` to a temporary directory.
2. **Version Pinning:** Checks out the exact target commit (e.g., `earlgrey_1.0.0`).
3. **Dynamic Discovery:** Dynamically finds all `.c`, `.h`, `.rs`, and `.sv` files within highly targeted critical paths (like `sw/device/silicon_creator/rom` and `sw/device/lib/crypto`).
4. **Tool-less Execution:** Feeds the discovered files directly to the Gemini CLI via standard input (stdin) to circumvent OS argument length limits and background service crashes during heavy batch jobs.

### Defining the Scope

To expand or reduce the scope of the threat model, simply modify the `TARGET_DIRS` array inside `run_threat_model.sh`:

```bash
# Define the specific subdirectories to include in the threat model
TARGET_DIRS=(
    "sw/device/silicon_creator/rom"
    "sw/device/silicon_creator/rom_ext"
    "sw/device/silicon_creator/manuf"
    "sw/device/lib/crypto"
    "sw/device/lib/base"
    "sw/otbn/crypto"
)
```
