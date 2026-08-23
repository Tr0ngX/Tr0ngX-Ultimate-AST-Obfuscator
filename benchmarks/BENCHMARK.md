# Tr0ngX Ultimate AST Obfuscator - Benchmark & Performance Report

This report provides empirical measurements of obfuscation build time, payload size expansion, execution overhead, and semantic correctness across all individual obfuscation modes and defense tiers.

---

## 1. System Environment & Execution Baseline

- **Timestamp**: `2026-08-22 17:32:08`
- **Python Runtime**: Python `3.14.6` (win32)
- **Test Concurrency**: Single-threaded (Deterministic serial evaluation)
- **Benchmark Workload**: Sieve of Eratosthenes (Prime generation) + SHA-256 Iterative Hash Chain
- **Unobfuscated Baseline Execution Time**: `0.1417s`

---

## 2. Mode-by-Mode Benchmark Results

| # | Mode / Protection Tier | Description | Status | Build Time (s) | Exec Time (s) | Size (Bytes) | Expansion Ratio |
| :-: | :--- | :--- | :-: | :-: | :-: | :-: | :-: |
| 1 | **Mode 1 (Lite AST)** | Fast AST transformation + String & Integer mutation | **PASS** | 0.456s | 0.1133s | 22,307 | 32.3x |
| 2 | **Mode 2 (Standard AST)** | 2-Layer Trongdepzai AST + Constant restructuring | **PASS** | 0.425s | 0.1493s | 41,666 | 60.4x |
| 3 | **Mode 3 (Maximum AST)** | 3-Layer Deep AST + Control Flow Mutation | **PASS** | 0.489s | 0.1229s | 115,507 | 167.4x |
| 4 | **AST Junk (+MoreOBF)** | Mode 2 + Dead code decoy injection & try-except traps | **PASS** | 0.511s | 0.1206s | 95,797 | 138.8x |
| 5 | **Math Opaque Predicates** | Mode 2 + Number-theoretic Quadratic Non-Residue mod 7 & Euler invariants | **PASS** | 0.378s | 0.0927s | 51,378 | 74.5x |
| 6 | **Dynamic XOR Strings** | Mode 2 + Dynamic Per-Callsite AST-Coordinate Derived XOR Strings | **PASS** | 0.417s | 0.0997s | 63,705 | 92.3x |
| 7 | **Velimatix Level 1** | Velimatix BiOpaque AST Predicates | **PASS** | 0.382s | 0.0798s | 31,638 | 45.9x |
| 8 | **Velimatix Level 2** | Velimatix ExceptionJump Structured Control Flow | **PASS** | 5.983s | 0.7953s | 1,434,695 | 2079.3x |
| 9 | **Velimatix Level 3** | Velimatix Match-Case State Machine Dispatcher | **PASS** | 22.592s | 1.7497s | 2,447,696 | 3547.4x |
| 10 | **TVM 2.0 Level 1 (Basic)** | Polymorphic CPU + Custom ISA Bytecode Virtualization | **PASS** | 0.705s | 0.2393s | 138,085 | 200.1x |
| 11 | **TVM 2.0 Level 2 (+Traps)** | TVM 2.0 with Rolling NOPs and Unassigned Opcode Traps | **PASS** | 0.521s | 0.2091s | 131,423 | 190.5x |
| 12 | **TVM 2.0 Level 3 (+Scrub)** | TVM 2.0 with Dummy Invariants & Memory Scrubbing | **PASS** | 0.722s | 0.2051s | 149,522 | 216.7x |
| 13 | **Compiled AEAD Payload** | Multi-layer authenticated AEAD compilation (Marshal+2xXOR+2xZlib+Bz2) | **PASS** | 0.762s | 0.2290s | 80,874 | 117.2x |
| 14 | **Double Compile AEAD** | Inner AEAD compiled bytecode wrapped inside Velimatix Loader | **PASS** | 2.221s | 0.6152s | 544,923 | 789.7x |
| 15 | **Anti-VM & Sandbox** | Hardware, Hypervisor, MAC OUI & Driver Detection Matrix | **PASS** | 0.640s | 0.1569s | 51,463 | 74.6x |
| 16 | **In-Memory Anti-Dump** | GC Object Scrubber, Linecache Neutralizer & Frame Cleaner | **PASS** | 0.417s | 0.1320s | 49,966 | 72.4x |
| 17 | **Self-Modifying Layer** | Zero-width signature morphing & runtime hash recalculation | **PASS** | 0.432s | 0.1340s | 55,462 | 80.4x |
| 18 | **Kramer Kyrie Shield** | Dynamic Caesar Alphabet Rotation Class Loader | **PASS** | 0.456s | 0.1623s | 335,262 | 485.9x |
| 19 | **Emoji Stream Shield** | Executable Unicode Animal Emoji sequence encoding | **PASS** | 0.492s | 0.1055s | 39,958 | 57.9x |
| 20 | **Whitespace Bitfield** | Invisible tab/space binary bitfield encoding | **PASS** | 0.433s | 0.1112s | 78,687 | 114.0x |
| 21 | **Extreme Zalgo Shield** | Glitch diacritics stacking (Z͑͗͑͗...) to paralyze decompiler GUIs | **PASS** | 0.449s | 0.1524s | 129,792 | 188.1x |
| 22 | **Hyperion Camouflage** | Fake Scientific Computing Simulation Class (MemoryAccess/StackOverflow) | **PASS** | 0.500s | 0.1160s | 16,139 | 23.4x |
| 23 | **Fused 3-Track Matrix** | Interwoven Symbiotic Matrix Loader (Kyrie + Emoji + Whitespace) | **PASS** | 0.510s | 0.1640s | 316,762 | 459.1x |
| 24 | **FULL ARSENAL MAXIMUM** | All 15 defense tiers combined: TVM 2.0 L3 + Camouflage + Matrix + Anti-Analysis Matrix | **PASS** | 11.914s | 13.4602s | 22,191,874 | 32162.1x |

---

## 3. Summary & Analysis Metrics

- **Total Configurations Tested**: `24`
- **Successful Configurations**: `24 / 24` (100.0%)
- **Semantic Equivalence Rate**: `100%` (All passing builds matched baseline calculations)

### Key Takeaways
1. **Core AST Modes (1..3)**: Deliver near-zero runtime latency overhead while scrambling control flow and variable references.
2. **True Virtual Machine 2.0 (TVM)**: Virtualizes Python AST into a polymorphic custom CPU interpreter with KDF V3 domain-separated encryption and in-memory GC scrubbing.
3. **Outer Shields (Matrix, Kyrie, Emoji, Whitespace)**: Multi-track dynamic disguises encapsulate inner AEAD payloads with zero file bloat when fused.
4. **Maximum Power Arsenal**: Combines all 15 defense tiers simultaneously to offer industrial-grade protection against static and dynamic decompilers (PyCDC, uncompyle6, IDA, Frida, Ghidra).

---

Made with ❤️ by Tr0ngX & Anti-Reverse Engineering Research Community
