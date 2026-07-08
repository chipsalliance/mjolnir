# OpenTitan Firmware Threat Model (Distilled)

This document provides a distilled, firmware-focused view of the threats identified in the comprehensive OpenTitan Earlgrey component-level threat model. It aggregates systemic vulnerabilities across the hardware/software boundary, eliminating module-by-module repetition to focus on actionable risks, architectural assumptions, and required mitigations for the firmware execution phases (ROM, ROM_EXT, and Manufacturing) and the `otcrypto` library.

## 1. Trust Boundaries & Assets

Firmware operates within the highly trusted core of the OpenTitan Root of Trust (RoT). However, its security relies entirely on defending the boundaries between mutable state, external interfaces, and hardware accelerators:

- **Immutable ROM (Highest Trust):** The hardware root of trust. Vulnerabilities here are unpatchable and compromise all subsequent stages.
- **ROM_EXT (Verified Trust):** The first mutable code stage. It bridges ROM and the Silicon Owner domain.
- **Cryptographic API Boundary (`otcrypto`):** The software abstraction layer that manages sensitive key material (blinded vs. hardware-backed) and orchestrates operations.
- **Hardware Crypto Coprocessors (OTBN, KMAC, AES, Keymgr):** Highly isolated execution environments. Firmware acts as an untrusted orchestrator passing parameters across the MMIO boundary.
- **Persistent State Memory (Semi-Trusted):** Retention SRAM, Flash Info Pages, and OTP memory. These bridge state across power cycles and resets, making them prime targets for Time-of-Check to Time-of-Use (TOCTOU) and data corruption attacks.
- **External Provisioning Interfaces (Untrusted):** SPI/UART consoles and JTAG/RV_DM, specifically during the manufacturing and individualization phases.

## 2. Key Threat Categories & Firmware Impact

### 2.1. Fault Injection (Tampering & Control Flow Hijacking)

**Threat:** Attackers utilizing voltage, clock, or electromagnetic glitching to disrupt the CPU pipeline, skip critical instructions, or flip registers evaluating security boundaries.

- **Firmware Impact:**
  - **Bypassing Cryptographic Verification:** Glitching the conditional branches evaluating signature validity (e.g., `rom_ext_verify`, `sigverify_otp_keys_check`). Firmware must aggressively utilize hardened booleans (`kHardenedBoolTrue`), redundant checks (`HARDENED_CHECK_EQ`), and instruction laundering (`launder32`) to resist single-fault instruction skips.
  - **Crypto Library (`otcrypto`) Integrity Bypasses:** Glitching the underlying cryptographic implementations to bypass basic crypto fault protections (such as keyblob checksum validations, padding checks, or looping bounds). The `otcrypto` library must strictly enforce FI mitigations such as `HARDENED_TRY`, redundant execution paths, and clearing sensitive CPU registers (e.g., `ibex_clear_rf()`) immediately after evaluations to prevent lingering spoofed "success" states.
  - **Lifecycle (LC) Downgrades:** Forcing the firmware to evaluate a `PROD` lifecycle state as `TEST` or `DEV`, subsequently tricking the ROM into authorizing "fake" or development public keys to verify malicious payloads.
  - **Bypassing Hardware Locks:** Glitching the execution flow before OTP partitions (e.g., `CreatorSwCfg`) or Flash Info pages are permanently locked via MMIO writes, leaving them mutable to lower-privileged execution stages.

### 2.2. Memory Safety & Buffer Exhaustion (Denial of Service & Privilege Escalation)

**Threat:** Exploiting software parsing logic or memory allocation to induce buffer overflows, out-of-bounds reads, or stack exhaustion.

- **Firmware Impact:**
  - **Variable Length Arrays (VLAs) on the Stack:** Several cryptographic implementations (`otcrypto_aes`, `kdf_ctr`, `ecc_curve25519`, `aes_kwp`) dynamically allocate stack arrays based on caller-supplied lengths. In a deeply constrained embedded environment, an attacker manipulating these length parameters will deterministically crash the stack, leading to a Denial of Service or potentially arbitrary code execution if stack canaries are bypassed.
  - **Untrusted TLV Parsing:** Manufacturing interfaces deserialize complex JSON or TLV payloads (e.g., `perso_tlv_data.c`) directly from the SPI console. Unbounded `memcpy` operations or missing length validations here present severe risks for memory corruption during the provisioning phase.

### 2.3. Cryptographic Data Remanence (Information Disclosure)

**Threat:** Sensitive cryptographic material (private scalars, intermediate states, decrypted blocks) lingering in hardware or software memory after an operation completes or fails.

- **Firmware Impact:**
  - **Early-Return Macro Vulnerabilities:** The pervasive use of `HARDENED_TRY()` on read/write operations with the OTBN or KMAC coprocessors creates a critical remanence vulnerability. If a hardware fault occurs, the macro forces an immediate return. This bypasses terminal cleanup functions (like `otbn_dmem_sec_wipe()` or `keymgr_sideload_clear_kmac()`), abandoning plaintext keys and intermediate states in accessible hardware registers or DMEM.
  - **Stack Leakage:** Cryptographic wrappers frequently unmask blinded key shares into local stack arrays (e.g., `unmasked_key` in HMAC or Ed25519 operations). If these arrays are not explicitly and securely zeroized (`hardened_memshred`) prior to returning—especially on error paths—the plaintext secrets leak into subsequent stack frames.

### 2.4. Cross-Reset State Manipulation (Spoofing & TOCTOU)

**Threat:** Manipulating memory regions that survive soft resets (Retention SRAM) to forge the device's historical execution state.

- **Firmware Impact:**
  - **Boot Log & Reset Reason Forgery:** Firmware relies heavily on `retram->creator.reset_reasons` and `boot_log` to drive state machines (e.g., entering rescue mode, advancing DICE chains, or processing Boot Services). If Retention SRAM lacks physical memory protection (ePMP) lockdown after early boot, a compromised OS can modify this state and trigger a soft reset, tricking the ROM_EXT into executing a malicious boot policy.
  - **Boot Services Abuse:** A compromised application could inject an unauthorized Boot Services message into Retention SRAM to force an anti-rollback downgrade or partition switch upon the next reboot.

### 2.5. Manufacturing & Supply Chain Vulnerabilities

**Threat:** Exploiting the provisioning environment or injecting test artifacts into production builds.

- **Firmware Impact:**
  - **Test Key Contamination:** The repository contains numerous "fake" SPHINCS+ and ECDSA keys used for testing. If the build system lacks strict, verifiable isolation, compiling these test keys into a production Mask ROM tape-out fundamentally compromises the Root of Trust.
  - **AST Calibration Tampering:** Calibration data stored in Flash Info pages dictates the operational boundaries of hardware security sensors (voltage droop, clock glitch detectors). If these values are tampered with or replaced by zero-values prior to hardware lockdown, an attacker effectively blinds the silicon's physical defenses, vastly increasing the success rate of subsequent FI attacks.

### 2.6. Cryptographic Library (`otcrypto`) Implementation Flaws

**Threat:** Exploiting logical flaws, asynchronous state gaps, or side-channel leakage within the cryptographic API layer to forge signatures or extract keys.

- **Firmware Impact:**
  - **Hardware-Backed Key Downgrades:** The API distinguishes between software-managed keys and hardware-backed keys (sideloaded directly from Keymgr to OTBN/AES/KMAC). Glitching the `hw_backed` conditional evaluations could coerce the library into treating a secure hardware key as a software key, attempting to extract it to accessible RAM, or vice versa.
  - **Asynchronous State Disruption:** Heavy operations offloaded to coprocessors are split into `_start` and `_finalize` routines. If an attacker interrupts execution between these phases, forces the host to abandon the operation, or triggers a failure before `_finalize` completes, sensitive cryptographic state remains active and exposed in the coprocessor memory without secure cleanup.
  - **Algorithmic & Integrity Bypasses:** Skipping deferred point-on-curve checks in ECC operations (Invalid Curve Attacks), exploiting non-constant-time padding verification in RSA OAEP/PSS (Bleichenbacher attacks), or forging the simplistic checksums on key structures via FI compromises the mathematical guarantees of the crypto library.
