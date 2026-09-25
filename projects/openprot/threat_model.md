<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OpenPRoT Firmware Threat Model

This document defines the architectural trust boundaries, high-value assets, adversary models, and primary threat vectors for the **OpenPRoT** Platform Root of Trust (PRoT) firmware stack.

## 1. Trust Boundaries & Core Assets

OpenPRoT provides a modular, multi-target Rust firmware stack operating across isolated microkernel tasks (Hubris, Tock, Pigweed `pw_kernel`, and baremetal targets on AST10x0, OpenTitan EarlGrey, and VeeR RISC-V). Security depends on defending the boundaries between external bus interfaces, unprivileged service tasks, IPC channels, and underlying hardware security engines:

- **External Bus & Wire Interfaces (Untrusted):**
  - I2C / I3C target buses, UART/USART consoles, and SPI flash busses exposed to the Host BMC, CPU, or physical peripheral headers.
  - All wire frames arriving over **MCTP** (Management Component Transport Protocol), **SPDM** (Security Protocol and Data Model), and **PLDM** (Platform Level Data Model) are controlled by potentially compromised external processors.
- **IPC & Service Isolation Boundary (Semi-Trusted):**
  - Services (`services/spdm`, `services/pldm`, `services/mctp`, `services/i2c`, `services/storage`, `services/telemetry`, `services/orchestrator`) communicate via zero-copy or serialized IPC buffers (`util/ipc`, `client-ipc`).
  - A compromised protocol parser must not be able to corrupt kernel state, forge caller task identities, or trigger out-of-bounds reads/writes in privileged server tasks (`server-runtime`).
- **Cryptographic & KeyVault HAL Boundary (High Trust):**
  - `hal/blocking` (`key_vault.rs`, `cipher.rs`, `digest.rs`, `ecdsa.rs`, `mac.rs`, `flash/`) and `platform/impls/rustcrypto` manage hardware-backed and software-held keys, attestation identities, and flash regions.
  - Key handles and slot indices must be strictly validated to prevent cross-tenant key usage or unauthorized key extraction.
- **Target Boot & SoC Integration Layer (Highest Trust):**
  - `target/ast10x0`, `target/earlgrey`, and `target/veer` configure hardware memory protection (MPU/ePMP), peripheral access crates (`ast1060-pac`, `ureg`), and bridge with Silicon RoT subsystems (`caliptra-sw`, `caliptra-mcu-sw`).

## 2. Key Threat Categories & Firmware Impact

### 2.1. Protocol Deserialization & State Machine Flaws (`services/mctp`, `spdm`, `pldm`, `i2c`)

**Threat:** Maliciously crafted packets sent by an untrusted BMC or host over I2C/MCTP/USART targeting protocol framing, length fields, fragmentation reassembly, or session state machines.

- **Firmware Impact:**
  - **Integer Overflows & Slice Panics in No-Std Rust:** In `no_std` embedded Rust without a global handler that recovers tasks cleanly, an unchecked slice index (`buf[offset..offset + len]`), arithmetic overflow on payload length, or `.unwrap()` on attacker-controlled wire bytes causes a task panic and deterministic Denial of Service (DoS) of the PRoT service.
  - **MCTP Packet Reassembly & Buffer Exhaustion:** Sending interleaved, truncated, or out-of-sequence MCTP fragments with spoofed source EIDs or message tags to exhaust static reassembly buffers, starve legitimate management traffic, or mix payload bytes across security contexts.
  - **SPDM Authentication & Session State Bypass:** Out-of-order SPDM commands (e.g., requesting measurements or key exchange completion prior to `GET_VERSION` / `NEGOTIATE_ALGORITHMS` / `DIGESTS` / `CHALLENGE` verification), session ID confusion, or downgrade to weak/empty cryptographic suites.
  - **PLDM Firmware Update Time-of-Check to Time-of-Use (TOCTOU):** Modifying staged firmware blocks in shared storage or flash between signature/digest verification and activation (`orchestrator` / `storage`).

### 2.2. IPC Boundary Violations & Lease Confusion (`util/ipc`, `*-ipc`)

**Threat:** A lower-privileged client task supplying malformed IPC headers, invalid buffer lengths, or aliased memory leases to a higher-privileged server (`i2c/server`, `storage`, `key_vault`).

- **Firmware Impact:**
  - **Confused Deputy via IPC:** A client task tricking the I2C or Flash server into reading/writing restricted hardware addresses or protected flash partitions on its behalf due to missing caller privilege or address-range checks.
  - ** Deserialization Truncation & Uninitialized Memory Exposure:** Returning partially populated response buffers over IPC without zeroing trailing padding bytes, leaking stack or heap secrets from the server task back to the client.

### 2.3. Cryptographic HAL & KeyVault Misuse (`hal/blocking`, `platform/impls/rustcrypto`)

**Threat:** Logical flaws in cryptographic trait implementations, key slot management, or error cleanup paths.

- **Firmware Impact:**
  - **Key Slot Index Out-of-Bounds / Unauthorized Export:** Passing an out-of-range or unauthenticated slot identifier to `KeyVault` operations, allowing a service to sign, decrypt, or derive data using a higher-privilege root key (e.g., DICE Alias/Attestation key).
  - **Secret Data Remanence on Error Paths:** Intermediate cryptographic states, unmasked key material, or plaintext buffers remaining in stack memory or static buffers when a `cipher`, `mac`, or `ecdsa` operation returns an early `Err(...)` without explicit zeroization (`zeroize`).
  - **Nonce / IV Reuse & Weak Randomness:** Reusing static or predictable nonces in symmetric encryption (`cipher.rs`) or deterministic ECDSA signing without hardware entropy verification.

### 2.4. MMIO, DMA, & Register Copy Safety (`util/regcpy`, `drivers/`, `target/`)

**Threat:** Unsafe memory-mapped I/O (MMIO) register accesses, volatile pointer arithmetic, or DMA descriptor misconfiguration.

- **Firmware Impact:**
  - **Unaligned or Out-of-Bounds MMIO Access (`unsafe` blocks):** `util/regcpy` and low-level drivers (`drivers/usart`, `target/ast10x0`, `target/earlgrey`) rely on `unsafe` pointer casts and volatile reads/writes. Misaligned lengths or unchecked byte counts can read/write past hardware FIFO registers into adjacent peripheral control registers.
  - **Flash Erase/Write Alignment & Bounds Bypass (`hal/blocking/flash`):** Missing sector alignment or partition boundary checks allowing a storage client to overwrite bootloader code, active configuration headers, or anti-rollback counters.
