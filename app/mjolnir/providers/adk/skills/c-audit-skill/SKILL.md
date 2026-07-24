---
name: c-audit-skill
description: Guidelines and check procedures for identifying vulnerabilities in embedded C/C++ codebase files.
---

# C/C++ Security Audit Guidelines

When analyzing C/C++ source files, pay special attention to the following language-specific vulnerabilities:

## 1. Memory Safety

- **Buffer Overflows & Underflows:** Scrutinize array indexing, pointer arithmetic, and loop bounds. Pay special attention to string handling and memory copy operations (e.g., prefer `snprintf` over `sprintf`, `strncpy` over `strcpy`).
- **Pointer Hazards:** Look for potential null pointer dereferences, use-after-free conditions, double frees, and dangling pointers.
- **Uninitialized Memory:** Ensure all variables, particularly pointers and buffers, are properly initialized before use.
- **Dynamic Memory Allocation:** If dynamic allocation is used (e.g., `malloc`, `free`), check for memory leaks and allocation failures. (Note: Embedded firmware often avoids dynamic allocation entirely).

## 2. Integer Overflows & Underflows

- **Type Conversions:** Watch out for dangerous implicit conversions, especially between signed and unsigned integers, or narrowing conversions.

## 3. Error Handling & Return Values

- **Exception Safety (if C++):** Ensure proper use of RAII (Resource Acquisition Is Initialization) and that exceptions (if enabled) do not leak resources or leave the system in an inconsistent state.

## 4. Pre-processor Macros

- **Macro Safety:** Check for pre-processor macros that lack proper parentheses around arguments and the whole expression, or that evaluate arguments multiple times causing side effects.
