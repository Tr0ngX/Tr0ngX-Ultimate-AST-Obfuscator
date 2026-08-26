# Findings — v5 Native-Core Refactor

## Measured facts (this machine, 2026-08)
- TVM runtime slowdown vs native: baseline x16.94 -> G1 x16.61 (slot-table hoist);
  loop_sum -33%, string_build -35%, closure -11%. Handler-call dominates remaining cost.
- Full-option build: 486s/8.6GB peak -> ~208s/~4GB after build-pipeline wave.
- MAXIMUM-POWER stack artifact fails at RUNTIME (RecursionError in TVM lazy-const
  resolve_const) - pre-existing, A/B-verified via git stash. W3 must fix (iterative resolver).
- Toolchain: rustc/cargo 1.98.0 stable-msvc; VS BuildTools 2022 + VC.Tools.x64 present;
  link-smoke PASS (0.29s, hello.exe runs). maturin 1.15.0, hypothesis 6.165.10,
  cryptography 48.0.1, pystyle 2.9, psutil 7.2.2, pytest 9.1.1.
- Missing: cargo-deny/audit (P6), PyOxidizer (W6), PyInstaller (check at exe-packaging time).

## Design decisions locked
- Single-engine: Rust = only semantic engine; portable .py embeds native blobs and
  self-extracts; emergency py-interpreter is auto-generated + CI trace-diff verified.
- IR schema v5: versioned, hashable, extensible tail fields (data[10]+ pattern proven).
- CPython ast stays the ONLY parser; Rust consumes serialized IR bytes.
- Crypto: ring ChaCha20-Poly1305 AEAD replaces TRXH HMAC-CTR handroll (v3/v4 dual-read).
- Anti-tamper split: Python shell keeps PEP578 canary; Rust does syscall/TEB layer.
- asm budget ~50 instructions total: TEB read + direct-syscall stubs only.

## Gotchas discovered (do not repeat)
- __builtins__ is a dict when module imported vs module under __main__ - always use
  explicit `import builtins` at BUILD time (broke every velimatix>=2 artifact post-split).
- Emitted-runtime templates: indentation must match HEAD exactly or artifacts break
  (G1 interp_fn lesson).
- Per-frame work in attach path scales with call count - cache per permutation identity.
- Slim binder (prefill params only) measured SLOWER than full dict-comprehension - reverted.

## Corpus / gates inventory (current main)
syntax parity 66/66 · coverage 156/156 · oracle 31/31 · fuzz 38/38 · test_01..14 green
(native); semantic parity test_02-05 byte-match; test_10 full-matrix 10/10; shields 6/6.
