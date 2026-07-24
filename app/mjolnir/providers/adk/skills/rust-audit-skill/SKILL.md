---
name: rust-audit-skill
description: Guidelines and check procedures for identifying vulnerabilities in embedded Rust codebase files.
---

# Rust Security Audit Guidelines

When analyzing Rust source files, pay special attention to the following language-specific safety paradigms and pitfalls:

## 1. Unsafe Code

- **Raw Pointers:** Scrutinize the use of raw pointers (`*const T`, `*mut T`) for potential memory safety issues (use-after-free, null dereference, buffer overflow).
- **Justification:** Ensure every `unsafe` block has a clear, documented justification explaining why it is safe.
- **Hardware Access:** Check for proper synchronization and memory barriers when accessing hardware registers via `unsafe`.

## 2. Integer Overflows & Underflows

- **Checked Arithmetic:** Prefer the use of checked (`checked_*`), saturating (`saturating_*`), or wrapping (`wrapping_*`) arithmetic where appropriate instead of wrapping-by-default behavior.

## 3. Panics & Error Handling

- **Panic Paths:** Identify code paths that could trigger a panic (e.g., `unwrap()`, `expect()`, out-of-bounds indexing) in critical firmware paths. Firmware should generally avoid panicking.
- **Result Handling:** Ensure all `Result` types are properly handled and not ignored.

## 4. Resource Management

- **Stack Usage:** Be mindful of deep recursion or large stack allocations that could lead to stack overflow in resource-constrained environments.
