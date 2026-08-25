# AGENTS.md - Developer & Agent Operational Handbook

Welcome to the **Tr0ngX Ultimate AST Obfuscator** codebase repository. This document serves as the authoritative operational manual and architecture guide for all AI Agents (Antigravity, Codex, Crush, Claude, etc.) and human contributors collaborating on this project.

---

## 1. Core Directives & Mandatory Rules for Agents

All AI agents operating on this repository MUST strictly abide by the following protocol:

1. **Documentation Synchronization (Strict Mandate)**:
   - Every time a new feature, new transformation pass, or new `--` command-line argument is added or modified in `main.py`, the agent **MUST immediately update** both `README.md` and `AGENTS.md` with:
     - The exact CLI argument syntax and choices.
     - A concise explanation of what the feature does and its position in the pipeline.
     - Updated CLI option tables and summary metrics.
2. **Emoji Policy in Documentation**:
   - Per repository design standards, markdown documentation (`README.md`, `AGENTS.md`, docs) MUST remain clean of emojis, with the sole exception of the footer:
     `Made with ❤️ by Tr0ngX & Anti-Reverse Engineering Research Community`
3. **Deterministic Compatibility & Zero-Crash Standard**:
   - Every obfuscation mode, loader, and cryptographic wrapper MUST execute flawlessly on **Python 3.10, 3.11, 3.12, 3.13, and 3.14** without syntax errors or runtime regressions.
   - Self-testing and assertion verification must pass with 100% success before handing over work.
4. **Git Discipline**:
   - Remove scratch or temporary test output files (e.g. `test_*.py` generated during testing) before committing.
   - Commit changes with clear, descriptive messages and push directly to `origin main`.
5. **Testing Concurrency Rule (Strict Prohibition)**:
   - **NEVER execute multi-threaded test harnesses** (e.g. `python tests/run_all_tests.py -w ...` or parallel worker jobs) WITHOUT EXPLICIT PERMISSION/COMMAND FROM THE USER.
   - All default test runs, validation, and self-testing MUST run in single-thread / single-process mode (`-w 1` or individual standalone target scripts) to avoid system overload and resource starvation.

---

### 1.5 Module Split (2026-08)

The former single-file engine is now a package. Root contains only `main.py` (entry point); all engines live under `tr0ngx/`:

| Module | Responsibility |
| :--- | :--- |
| `tr0ngx/config.py` | `_EngineState`, console setup, shared mutable globals (access via attribute style) |
| `tr0ngx/names.py` | `rd()` + chemical/CJK/homoglyph/rare-unicode/Zalgo generators, `_gen_exotic_name` |
| `tr0ngx/velimatix.py` | Velimatix transformer suite + dead-code/string-encoder |
| `tr0ngx/astpasses.py` | opaque predicates, dyn-strings XOR, decompiler traps/var-split, obfstr/obfint, `obf()`, ANTI_PYCDC |
| `tr0ngx/shields.py` | anti / velimatix_anti_hook templates, self-modify + anti-vm generators |
| `tr0ngx/crypto.py` | AEAD v3, KDFs, armor codec, `_multi_layer_encrypt`, `_double_compile` |
| `tr0ngx/vm.py` | TVM: opcodes, code objects, AST compiler, runtime emitter, `_vm_obfuscate` |
| `tr0ngx/packagers.py` | emoji/ws encoders, Kramer/Kyrie, Hyperion camouflage, fused matrix, exotic wrap |
| `tr0ngx/diagnostics.py` | banners, logger, profiler waterfall, debug map, peak-RSS sampler |
| `tr0ngx/pipeline.py` | stage orchestrator (`obfuscate_single_target`) |
| `tr0ngx/cli.py` + `tr0ngx/tui.py` | argparse entry (`main()`) and interactive TUI flows |
| `tr0ngx/exotic.py` | BitMatrix byte chain + Base4096 glyph encoder |

Invariant for future edits: cross-module access to MUTABLE state (`_EngineState`, `_DEBUG_MAP`, ...) must go through module attribute access (`from . import config as _cfg; _cfg._EngineState`) - never from-import rebindable globals. Build-time code must resolve builtins via the explicit builtins MODULE (`import builtins`), never the context-dependent `__builtins__` (dict when imported, module when run as __main__).

## 2. System Architecture Overview

Tr0ngX is an industrial-grade, multi-stage Python AST Obfuscator combining advanced compiler theory, control flow flattening, cryptographic authenticated loaders, dynamic outer shields, and decompiler crash mechanics.

### Pipeline Execution Order

```mermaid
graph TD
    A[Source Python File] --> B[0. Hyperion Token & Builtin Remapping Engine]
    B --> C[1. AST Syntax Transformations & Normalization]
    C --> D[2. AST Dead Code & Junk Injection]
    D --> E[3. Anti-Analysis Matrix: Anti-Debug, Anti-Hook, Watchdog, Self-Mod]
    E --> F[4. Velimatix AST Engine: BiOpaque, Exception Jump, Match-Case, Builtin Rename]
    F --> G[5. Trongdepzai AST Multi-Layer Obfuscator Layers 1..3]
    G --> H[6. VM Virtualization Engine: Polymorphic CPU, Randomized ISA & Encrypted V-Bytecode]
    H --> I[7. Multi-Layer AEAD Bytecode Compilation: Marshal + 2x XOR + 2x Zlib + Bz2 + Base85]
    I --> J[8. Double Compile: Inner Bytecode wrapped in Velimatix Loader]
    J --> K[9. Dynamic Outer Shields: Fused Matrix / Kramer Kyrie Eleison / Emoji / Whitespace]
    K --> L[10. Hyperion Camouflage: Fake Scientific/Algorithmic Class Simulator]
    L --> M[11. Unicode Glitch Shields: Extreme Zalgo Diacritics Stacking & Ancient Hieroglyphs]
    M --> N[Final Obfuscated Output Script]
```

---

## 3. Comprehensive CLI Flag Reference

| Flag | Category | Description | Choices / Format |
| :--- | :--- | :--- | :--- |
| `-i`, `--input` | IO | Target Python script(s) or glob patterns to obfuscate | `<filepath(s) / glob>` |
| `-D`, `--dir`, `--directory` | IO | Target directory containing Python files to batch obfuscate | `<dirpath>` |
| `-r`, `--recursive` | IO | Recursively scan all subdirectories when batch obfuscating | Flag |
| `-w`, `--workers`, `-j` | Resource | Number of parallel worker threads for concurrent batch obfuscation | e.g. `4`, `8` |
| `-o`, `--output` | IO | Custom output file destination (or output directory for batch) | `<filepath / dirpath>` |
| `-m`, `--mode` | Core AST | AST obfuscation complexity level | `1`, `2`, `3` |
| `--moreobf` | Core AST | Inject extra AST dead code and try-except decoy blocks | `y` / `n` |
| `--antidebug` | Protection | Inject anti-debugging watchdog daemon, Win32 PEB/remote debug checks, and hook blockers | `y` / `n` |
| `--antivm` | Protection | Inject Anti-VM, Automated Sandbox & Virtual Network Adapter Detection matrix (MAC OUI, virtual NICs, SCSI disks, drivers, registry) | `y` / `n` |
| `--anti-dump` | Protection | Inject in-memory anti-dump shield, GC object scrubber, and code metadata neutralizer | `y` / `n` |
| `--selfmod` | Protection | Inject runtime signature mutating self-modification layer | `y` / `n` |
| `--math-opaque` | Core AST | Inject number-theoretic mathematical opaque predicates (Quadratic Non-Residues mod 7, Euler invariants) | `y` / `n` |
| `--dyn-strings` | Core AST | Dynamic per-callsite string XOR encryption with AST-coordinate derived keys | `y` / `n` |
| `--dec-trap`, `--dectrap` | Core AST | Inject decompiler control flow traps & opaque CFG blocks (crashes uncompyle6, decompyle3, pycdc) | `y` / `n` |
| `--var-split` | Core AST | Split local integer variables into dynamic XOR secret shares (v1 ^ v2) | `y` / `n` |
| `--str-frag` | Core AST | String fragmentation v2 with decoy chunks and dynamic runtime assembly | `y` / `n` |
| `--debug-poison` | Protection | Deceptive debug poison state machine (silent key degradation on debugger/sandbox detection) | `y` / `n` |
| `--spoof-meta` | Protection | Metadata & `co_filename` spoofing (camouflages stack traces to stdlib modules) | `y` / `n` |
| `--compile` | Crypto | Multi-layer authenticated AEAD compilation (Marshal + XOR + Zlib + Bz2) | `y` / `n` |
| `--password` | Crypto | Password for Argon2id + ChaCha20-Poly1305 AEAD / PBKDF2 (600k) payload encryption. Password mode REQUIRES the `cryptography` package and hard-fails otherwise (no silent downgrade) | `<string>` |
| `--password-file` | Crypto | Path to external file containing encryption password (missing/empty file aborts with exit 2) | `<filepath>` |
| `--exotic-pools` | Identifiers | Identifiers drawn from rare Unicode script pools (Tangut, Egyptian Hieroglyphs+Ext-A, CJK Ext-G/H, Anatolian, Bamum, Glagolitic, Miao, Vedic); XID + NFKC validated via `tr0ngx_exotic.py` | `y` / `n` |
| `--base4096` | Exotic Encoding | Pack payload into 12-bit groups mapped to a 4096-glyph exotic alphabet with standalone inline decoder | `y` / `n` |
| `--bit-matrix` | Exotic Encoding | Multi-round invertible byte chain: LCG-XOR stream, bit rotation, nibble swap, Fisher-Yates S-Box, position mask | `y` / `n` |
| `--lzma-layer` | Crypto | LZMA (preset 9) pre-encryption compression stage inside `_multi_layer_encrypt`; decode chain mirrors per-build armor metadata | `y` / `n` |
| `--vm-annotations` | VM | Preserve type annotations in VM bytecode: module/class/function `__annotations__` dicts populated; enables dataclasses/pydantic/FastAPI under virtualization. Default off (reduces size) | `y` / `n` |
| `--anti-intercept` | Protection | Deep Anti-Read Shield: 5-layer network/memory/introspection protection — module import block (mitmproxy/scapy/frida), socket integrity snapshot + encrypted I/O wrapper, SSL CA pinning + localhost proxy detection, GC scrub, process watchdog scanning `/proc` for packet capture tools | `y` / `n` |
| `--env-key` | Crypto | Hardware fingerprint lock for no-password builds: transmitted salt XOR-blinded with sha256(node/system/machine/impl/ver); wrong machine fails authentication. Mutually exclusive with password modes (auto-disabled with warning) | `y` / `n` |
| `--verify` | Diagnostics | Post-build semantic differential: runs original + obfuscated outputs, compares stdout and exit codes; mismatch logged as `13_verify_semantic` stage error | `y` / `n` |
| `--shared-symbols` | Batch | Two-phase cross-module symbol sync for `-D/-r` batches: phase A parses all targets single-threaded and freezes one deterministic rename (`sha256(seed\|name)` derived) per symbol imported across files into `tr0ngx_shared_symbols.json`; phase B workers consume the immutable map via Hyperion token renamer | `y` / `n` |
| `--max-output-size` | Resource | Maximum output file size DoS limit (aborts and removes if exceeded) | e.g. `10MB`, `50MB` |
| `--seed` | Core AST | Deterministic seed for reproducible builds | e.g. `1337` |
| `--velimatix` | Velimatix | Enable Velimatix ExceptionJump & AST control flow engine | `y` / `n` |
| `--veli-level` | Velimatix | Velimatix intensity level (1: BiOpaque, 2: Exception Jump, 3: Match-Case State Machine) | `1`, `2`, `3` |
| `--vm-obf` | Core VM | Enable VM Virtualization Engine (Polymorphic Virtual CPU + Encrypted Bytecode) | `y` / `n` |
| `--vm-level` | Core VM | VM Virtualization intensity level (1: Basic, 2: + Traps/NOP, 3: + Dummy/Scrub) | `1`, `2`, `3` |
| `--double-compile` | Crypto | Package inner compiled bytecode inside outer Velimatix loader | `y` / `n` |
| `--kramer` | Outer Shield | Wrap with Kramer Kyrie Eleison outer dynamic shield class | `y` / `n` |
| `--matrix`, `--fused` | Outer Shield | Enable 3-Track Symbiotic Interleaved Matrix Shield (Kyrie + Emoji + Whitespace) | `y` / `n` |
| `--emoji-obf` | Outer Shield | Encode output payload as executable Unicode Animal block identifier stream | `y` / `n` |
| `--whitespace-obf` | Outer Shield | Encode output as invisible whitespace bitfields (space/tab binary) | `y` / `n` |
| `--blank-padding`, `--blank-lines` | Outer Shield | Prepend 300+ blank screen lines padding to conceal code in text editors | `y` / `n` |
| `--cjk-vars` | Identifiers | Use CJK Chinese identifiers and PyCool ancient docstrings | `y` / `n` |
| `--homoglyph` | Identifiers | Use Cyrillic/Greek lookalike variable names (a→а, o→о, e→е) | `y` / `n` |
| `--rare-unicode` | Identifiers | Use Rare Unicode characters (CJK Ext-B, Kangxi Radicals, Hieroglyphs) | `y` / `n` |
| `--zalgo`, `-z` | Glitch Shield | Enable Extreme Zalgo Combining Marks Shield (Heavy Diacritics Stacking - `Z͑͗͑͗...`) | `y` / `n` |
| `--hyperion` | Hyperion | Enable Full Hyperion Engine (Builtins remapping, token variable remap, math/str splitting, chunk shells) | `y` / `n` |
| `--camouflage`, `--camo` | Camouflage | Wrap in Hyperion Fake Scientific Simulation Class (`MemoryAccess`, `StackOverflow`, `Theory`, etc.) | `y` / `n` |
| `--force-py` | Environment | Multi-vector anti-spoof Python runtime & opcode architecture lock (`off` to disable) | `3.10`, `3.11`, `3.12`, `3.14`, etc. |
| `--max-ram` | Resource | Limit maximum RAM consumption in megabytes | e.g. `2048` |
| `--cores` | Resource | Limit maximum CPU cores/threads utilized | e.g. `2`, `4` |
| `--debug-map` | Diagnostics | Export JSON mapping of renamed symbols and stage durations | `AUTO` or `<path>` |
| `--debug`, `-d` | Diagnostics | Verbose stage logging and tracebacks | Flag |
| `--profile` | Diagnostics | Display detailed Profiling Waterfall & Bottleneck table | Flag |
| `--log-file` | Diagnostics | Write diagnostic execution logs to external file | `<path>` |
| `--strict` | Diagnostics | Abort immediately on any stage warning or non-critical error | Flag |
| `--no-art`, `-q` | UI | Suppress ASCII art banners and styling for headless CLI/Agent environments | Flag |

---

## 4. Key Subsystem Details

### 4.1 Hyperion Engine (`--hyperion`)
- **AddBuiltins**: Scans token AST, extracts all builtins referenced in code, and prepends explicit imports (`from builtins import ...`) to enable dynamic namespace redirection.
- **CreateVars & Scope Remapper**: Generates randomized variables for runtime primitives (`globals`, `locals`, `vars`, `__import__`, `getattr`, `dir`, `exec`, `eval`, `compile`, `unhexlify`, `join`, `bool`, `str`, `float`).
- **Math & String Identifier Splitting**: Transforms numeric constants into arithmetic algebraic identities (`val = rnum - (rnum - val)` with underscore notation `1_2_3_4`) and encodes strings through arithmetic reverse step slicing (`[::-+-(-1)]`).
- **Chunk Shell Encapsulation**: Partitions top-level statements into isolated valid AST chunks, each encapsulated inside `eval(compile(..., mode='exec'))`.

### 4.2 Hyperion Camouflage Layer (`--camouflage`)
- Replaces the outer file structure with an authentic-looking algorithmic or scientific computing class (`MemoryAccess`, `StackOverflow`, `Theory`, `Calculate`, `Hypothesis`).
- Creates mock mathematical methods, `@property` simulated memory addresses (`<__main__.MemoryAccess object at 0x000007FF...>`), and fake `try...except` exception handlers.
- Slices the obfuscated binary payload into Base85 parameter chunks stored as class properties and seamlessly reconstructs the payload at runtime.

### 4.3 Extreme Zalgo Combining Marks Shield (`--zalgo`, `-z`)
- Employs valid Python PEP 3131 Unicode identifiers utilizing `XID_Continue` characters (`Mn`/`Mc` diacritics in `U+0300..U+036F`, `U+1AB0..U+1AFF`, `U+1DC0..U+1DFF`, `U+20D0..U+20FF`, `U+FE20..U+FE2F`).
- Stacks 25 to 60 combining diacritical marks onto each variable character (`Z͑͗͑͗...`), overwhelming the text rendering engines of GUI editors, decompiler GUIs, and disassemblers (DirectWrite, HarfBuzz, FreeType, Scintilla).
- Injects massive cascading glitch text docstrings at the payload boundaries.

### 4.4 Fused Symbiotic Matrix Shield (`--matrix`, `--fused`)
- Interweaves three distinct disguise tracks into a single unified stream:
  1. Kyrie Eleison Alphabet Rotation + Dynamic Caesar Offset.
  2. Masked Unicode Emoji Stream (`U+1F400` Animal & Symbol block).
  3. Invisible Space/Tab Bitfield Matrix.
- Uses a deterministic Linear Congruential Generator (LCG) PRNG state to interleave and reconstruct tracks in memory with zero file-size bloat.

### 4.5 Polymorphic VM Virtualization Engine (`--vm-obf`, `--vm-level`)
- **Virtual CPU & Polymorphic ISA**: Compiles AST statement chunks into encrypted bytecode blocks (`marshal` + rolling XOR + Base85), executed by a lightweight runtime virtual interpreter.
- **Randomized Opcode Matrix**: Opcode byte assignments (`V_EXEC`, `V_HALT`, `V_NOP`, `V_TRAP`, `V_SCRUB`) are generated fresh per build across a 256-value space.
- **Visual Camouflage Integration**: VM registers, program counters, data pools, and dispatchers utilize the repository's hostile identifier matrix (Zalgo, CJK, Homoglyph, Rare Unicode, Invisible).
- **Anti-Analysis Trap Network**: Level 2+ injects rolling NOP sequences (p=0.15) and unreachable dead traps (1-3x, random 16-bit args) after RETURN/HALT/RAISE. Level 3 adds dummy LOAD_CONST/POP_TOP cycles (p=0.10) plus post-frame scrub (`stack/exc_handlers.clear()`). NOTE: "decoy encrypted chunks" and "GC zeroing" are NOT implemented - scrub is dict/list `.clear()` only; docs corrected 2026-08 after audit.
- **Full Language Coverage (TVM 3.0)**: real resumable generators (lazy iteration, send/throw/close, multi-level yield-from with return capture), full async surface (await hand-off on the running loop, async-for via a sentinel-free `__vm_anext__` tuple protocol, async-with, async generators, async comprehensions desugared into inline awaited helpers), positional defaults evaluated once at function creation (native semantics), correct `import a.b as c` submodule binding, `raise X from Y` cause propagation, dict-literal insertion-order preservation, and interpreter-internal builtin isolation (`_sys_len`) so user shadowing of builtins cannot corrupt the VM.
- **Level 4 Infrastructure**: deterministic per-name 256-byte ISA permutation implemented end-to-end (serializer substitution + runtime inverse dispatch), currently gated OFF pending unique per-code-object salts; at present `--vm-level 4` executes identically to level 3.

### 4.7 TVM Correctness Wave (2026-08, VM upgrade plan Phase 0/1 partial)
All fixes verified: oracle 31/31 + coverage 156/156 + syntax_parity 66/66 + fuzz 38/38.
- `visit_AsyncFunctionDef` never finalized/stored its code object -> UnboundLocalError on EVERY async def under `--vm-obf`. Now mirrors visit_FunctionDef (kwonly-default preamble included).
- Positional-only params (`/`) concatenated into signatures everywhere; binding order fixed; runtime keyword-rejection enforced via serialized `posonly_count` field.
- `emit()` raises typed `TVMEmitError` on args outside 16-bit range (was silent truncation corrupting jumps).
- `_vm_obfuscate` parse failure records `6.5_optimization_pass` stage error (respected by `--strict`) + loud warning.
- Stale-handler fix: compiler tracks `exc_frame_depth`; break/continue crossing try/with boundaries emit matching POP_BLOCK.
- Import forms fixed (GAP-29/30/31): from-imports return SUBMODULE via tokenized sentinel in `_h_imp_n`; dotted-as binds submodule; star imports via `__tvmstar__` sentinel + `__tvm_star_load__` helper respecting `__all__`; relative imports via level-aware package resolution through caller `__package__`.
- Arity enforcement (GAP-26/27): binder raises native-shaped TypeError on surplus positionals / unknown kwargs / missing required args after default application. Exemptions: synthetic names and kwonly-with-default params (serialized via `kwonly_default_names` code-object field).
- except* (PEP 654) fully implemented via `__tvm_excg_split__` runtime helper calling `ExceptionGroup.split()`; remainder chains across handlers; compile-time prohibitions enforced.
- Match-case hardening (GAP-33/34/35/36): sequence/mapping protocol checks (`__tvm_is_seq`/`__tvm_is_map`); kwd-attr miss = pattern-fail; positional index beyond `__match_args__` clean-fail; MatchOr capture snapshot/rollback.
- Finally-splice on return/break/continue (GAP-02): compiler `_fin_stack` deep-copies finalbody before RETURN/JUMP so cleanup always runs.
- Closure late-binding fix (GAP-19/20): `_h_ld_drf`/`_h_ld_g` prioritize active frame walk over captured_env stale snapshot.
- Known deferred: TVM crypto-envelope v4 rolled back pending clean re-land; closure cell boxing; module-level annotations GET_ITEM edge case.

### 4.7.1 TVM Anti-Fingerprint Hardening (2026-08, Phase G/R)
Landed (verified: oracle 31/31 + coverage 156/156 + fuzz 38/38 + reproducibility):
- Debug-map stage name neutralized: `6.5_optimization_pass` (level in `details` only).
- `TRX_VM_DEBUG` env probe removed entirely from emitted artifacts.
- Trap-delay randomized per build (0.01-0.15s before `_exit`).
- sys.monitoring: free-slot scan via `get_tool()` + per-build random tag (`tx` + sha256 prefix) instead of squatting all 6 slots with self-identifying `'trx_tvm_N'`.
- Magic-string tokenization (Phase G4): ALL semantic tokens randomized per build via `_TVM_TOKENS` dict shared between compiler and emitter: `'__TVM_LAZY__'`, `'_NO_ARG'`, `'__vm_await__'`, `'__vm_anext__'`, `'__vm_match_rest__'`, `'__vm_bind_defaults__'`, `'__tvmfl__'` — zero occurrences in artifact plaintext.
- Known remaining leaks (documented honestly): `TRX_TVM_ENC_KEY_V3:` / `TRX_TVM_MAC_KEY_V3:` KDF labels (2 occurrences, protocol requirement); `_h_*` handler names (deferred TVM 5.1 — requires pre-emission rename to avoid meta-packet deserialization mismatch).

### 4.6 Research Hardening Wave (2026-08, sourced from research_repos analysis)
Attribution policy: techniques are re-implemented independently; source repos credited inline as `Source:` comments. No GPL/AGPL/no-license code was copied (see license matrix in the research report): MIT/Apache sources are concept-level only unless noted.

Fixes applied (audit P0/P1):
- Anti-debug Vector 15 audit-canary self-defeat: real `sys.addaudithook` is snapshotted before nulling and the canary registers through the preserved reference.
- TRXH no-password MAC mismatch: `_derive_runtime_keys` no longer derives a separate pbkdf2 MAC key; every loader verifies with `sha256(ke + b'__mac__')`, matching the encryptor.
- `_double_compile` SyntaxError no longer silently returns plaintext; it records `7_double_compile_syntax_error` (respected by `--strict`) and warns.
- Unsupported-Python guard exits with code 1 (was 0).
- Scrub loops that zeroed a bytearray COPY of immutable bytes removed; honest del+gc cleanup documented.
- Camouflage license label corrected to EPL-2.0 (upstream Hyperion provenance).
- Velimatix ExceptionJump (`veli>=2`): sparse non-contiguous dispatcher states + sentinel exit (anti index-sorting reversal); `ast.Nonlocal` hoisted alongside `Global`.
- Batch input discovery: case-insensitive `.py/.pyw`, venv/site-packages/node_modules/build-dir blacklist.

New capabilities:
- Armor codec diversification + reversed payload storage inside `_multi_layer_encrypt`; all four emitted loader families mirror the chosen chain via interpolated metadata.
- LZMA pre-encryption layer, hardware env-key salt blinding, built-in `--verify` semantic differential, two-phase batch shared-symbol map, seeded ASCII identifier stream (`--seed`), anti-debug Vectors 19/20, 7-family opaque predicates, weighted heterogeneous string ciphers + exact float ratio reconstruction, exception-frame eligibility sniffing for decompiler traps.

### 4.8 Performance Hardening Wave (2026-08, profiled full-option build)
Baseline measured on a 673-byte input with every option enabled: 486s total, 8.6GB peak RSS. Bottleneck attribution (debug map + external RSS sampling): fused matrix shield 181s / peak 8.6GB (redundant CPython `compile()` of an already-sealed loader), VM engine 107s and 12MB to 235MB expansion, double-compile 78s with multi-GB parser spikes.

Changes (strength-neutral - all crypto layers, VM ISA randomization, trap/NOP rates, junk densities and opaque predicate families untouched):
- `_fused_matrix_wrap(already_packaged=...)`: when the payload is already a sealed loader (double-compile ran), the redundant marshal `compile()` pass is skipped; a TEXT-MODE terminal decoder variant execs the decompressed utf-8 source directly instead of `marshal.loads`. Track tables (Kyrie rotation+Caesar, emoji XOR mask, whitespace bitfield) are precomputed per-symbol; LCG state sequence and track interleaving are bit-identical (verified old-vs-new over randomized trials). Loader assembled by direct interpolation, removing three whole-payload `.replace()` scans.
- `_emoji_encode_v2` / `_whitespace_encode_v2`: same `already_packaged` fast path plus table-driven bit expansion.
- `_double_compile`: armored payload embedded as 8 joined literal parts (mirrors the standard-packaging pattern) instead of one giant literal, shrinking CPython parser arena on both password and no-password loader variants.
- `varsobf` validates via eval-mode parse; `_MainAstTransformer.visit_Constant` parses obfuscation expressions with `mode='eval'`, skipping the discarded Module+Assign wrapper nodes.
- FIXED pre-existing defect found during verification: fused-matrix loader template indented the `{_vars_}` statement one level deeper than its `return` sibling (IndentationError at runtime); normalized to match previously shipped artifacts.
- Debug map honesty: every stage entry now includes `peak_ram_mb` (true in-stage RSS maximum from a 4Hz daemon sampler); `ram_mb` remains end-of-stage RSS.

Measured result on the same 673-byte full-option build: total time 486s -> ~208s (-57%), peak RSS 8.6GB -> ~4.0GB (-54%); fused matrix stage alone 181s/8.6GB -> 32s/~3GB. VM engine now actually completes on async targets instead of silently skipping.

Bugs unmasked and fixed while re-verifying with the VM stage actually running (all were pre-existing; previously masked because `6.5_optimization_pass` crashed and the pipeline continued WITHOUT virtualization):
- `visit_AsyncFunctionDef` referenced an undefined `_fn_code` when serializing `kwonly_default_names` -> NameError on EVERY async def with kwonly defaults under `--vm-obf`; now mirrors `sub_compiler.code_obj.kwonly_default_names` like the sync visitor.
- `_h_ld_drf` had no `captured_env` fallback (unlike `_h_ld_g`), so closures invoked AFTER their enclosing frame returned raised `NameError: free variable ...`; fallback added.
- Closure environments were snapshot copies at MAKE_FUNCTION time, so sibling closures never saw each other's nonlocal writes after the factory returned (native Python shares live cells). Replaced with a live `_EnvChain` delegating to the defining frames' real locals dicts. The chain is sentinel-transparent: unfilled binder slots (`no_arg_sig`) read as absent, preventing a child comprehension/function from observing a bare sentinel value (this transparency fixes the walrus-in-comprehension `<object> < int` crash in test_10 Check 10).
- Anti-debug Vector 11 false positive (P0): bare `'id'` in `_BAD_CLASSES` substring-matched `Chrome_WidgetWin_1` - the window class of every Chromium/Electron app - so protected scripts self-terminated (`os._exit(1)`, silent) on ordinary developer desktops whenever `--antidebug y`. Entry removed; real debugger classes remain covered. Verified old build fails identically via git-stash A/B.

Known remaining limitation (pre-existing, documented honestly): a MAXIMUM-POWER stack artifact (`-m 3` + all shields + zalgo + hyperion + lzma) still fails at RUNTIME (RecursionError inside TVM lazy-const `resolve_const`, or silent exit on older builds). Confirmed identical failure on the pre-change build via git stash; unrelated to this wave. Track separately from TVM crypto-envelope/cell-boxing work.

---

### 4.9 TVM Performance Wave (2026-08, branch perf/tvm-runtime)

Strength-neutral runtime speedups for TVM-virtualized artifacts (all ISA
randomization, trap/NOP rates, junk densities and crypto untouched):

- G1 commit 8a4df11: dispatch slot table precomputed once per permutation
  (`_slot_cache`, M/A are build-constant) instead of recomputing the affine
  transform every instruction; `type(_sig) is tuple` in both eval loops;
  `gc.collect()+gc.freeze()` after payload load; ld_drf frames-walk made
  sentinel-transparent. Measured (benchmarks/vm_bench.py, BENCH_RUNS=9,
  back-to-back A/B): geomean slowdown x16.94 -> x16.61; loop_sum -33%,
  string_build -35%, closure -11%, fib -5%, miller -9%. Honest rejection:
  a slim binder (prefill params only) measured SLOWER than the C-level dict
  comprehension over local_names and was reverted.
- G2 commit 7f28170: compiler-certified global loads (declared via
  `global x`) record their name index in the serialized code object
  (data[10]) and skip the O(depth) frames-walk in _h_ld_g; duplicated
  captured_env block removed. ~2% additional, direction-consistent, within
  noise. Implicit module-level names keep the walk by design.
- G3: --force-py accepts a floor range (3.12+) - structural/hexversion/
  Py_GetVersion vectors switch to >= semantics while per-version opcode and
  magic-range probes stay armed; exact pins behave exactly as before.

Invariant: emitted runtimes remain stdlib-only and byte-compatible with the
existing loader families; serializer gained an optional trailing field
(data[10]) that old readers ignore.

---

## 5. Verification & Testing Protocol

Before committing any modifications:
```bash
# 1. Run single-thread regression verification (DO NOT USE -w multi-threading without user permission)
python tests/test_01_core_features.py

# 2. Run complex challenge paradigm test in single-thread mode
python main.py -i tests/test_10_complex_realworld.py -o test_full_matrix.py -m 2 --compile y --double-compile y --velimatix y --veli-level 2 --vm-obf y --vm-level 3 --matrix y --camouflage y --math-opaque y --dyn-strings y --no-art

# 3. Verify execution of obfuscated target
python test_full_matrix.py

# 4. Clean up generated test artifacts
powershell -Command "Remove-Item -Force -ErrorAction SilentlyContinue test_full_matrix.py"
```

### 5.1 Test Harness Contract (tests/run_all_tests.py)
- Default worker count is **1** (repo policy). `-w N>1` remains available but requires explicit opt-in.
- Phase 2 performs a real **semantic differential**: native stdout (captured in Phase 1) must byte-match obfuscated output (`SEMANTIC_DIFF` failure otherwise).
- Every subprocess carries a hard timeout: build 420s, runtime 120s, native suites 600s.
- Suites wired into the harness: `test_01..test_05`, `test_10`, `test_11_negative_inputs`, `test_12_combo_matrix`, `test_13_debugmap_roundtrip` (Phase 1/2); `test_06..test_09`, `test_14_exotic_module`, `test_vm_oracle_semantic`, `test_qa_fuzz_semantic` (Phase 3 standalone).
- `test_qa_fuzz_semantic.py` runs a REAL mutation fuzzer (>=300 malformed VM packets per run, seeded) and FAILS the suite on any unhandled crash.

### 5.2 Crypto Reality Check (post-hardening)
- `TRXA` payload magic = ChaCha20-Poly1305 AEAD; `TRXH` = legacy HMAC-SHA256-CTR fallback (obfuscation-only, no-password builds without `cryptography`).
- Argon2id t=3 m=64MiB p=2; PBKDF2-HMAC-SHA256 600,000 iterations.
- No-password mode derives keys from interpreter environment: tamper-resistance, NOT confidentiality.

---

Made with ❤️ by Tr0ngX & Anti-Reverse Engineering Research Community
