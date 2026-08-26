# Task Plan: Tr0ngX v5 Native-Core Refactor (single-engine, Windows-first)

## Status: IN_PROGRESS
## Goal: Rust core + Python shell, 3 output formats (.py / .pyc / .exe), zero functionality loss, parallel multi-agent execution

---

## Phase W0: Foundations — **Status: complete**
- [x] A1 planning-files v5 + archive TVM-5.0 plan
- [x] A2 link-smoke: rustc 1.98.0 / cargo 1.98.0 / MSVC link PASS; hypothesis 6.165.10
- [x] A3 Golden-Corpus seeds (tests/corpus/, 60 cases + manifest)

## Phase W1: Output formats py/pyc/exe (parallel agents) — **Status: in_progress**
- [x] B1 `tr0ngx/packagers_pyc.py` (agent-owned new file)
- [x] B2 `tr0ngx/packagers_exe.py` PyInstaller onefile, clean error if absent (agent-owned)
- [x] MAIN wire `--out-format {py,pyc,exe}` into cli.py + options dict + pipeline write path
- [ ] Gate-W1: test_01 PASS · semantic parity test_02-05 · pyc smoke run · exe smoke (PyInstaller present) · full legacy suite untouched

## Phase W2: trx-ir + serializer dual-impl — **Status: pending**
- [ ] IR schema v5 freeze (hashable, versioned, data[10]+ extensible)
- [ ] Rust reader byte-equal vs Python writer on corpus

## Phase W3: TVM native dispatcher shadow-mode — **Status: pending**
- [ ] eval_frame/binder port; lazy-const ITERATIVE resolver (kills MAXIMUM-POWER RecursionError)
- [ ] trace-diff harness L2(b); 14-night green gate before default flip
- [ ] TRX_CORE=python|native env switch; python stays default until green

## Phase W4: Crypto envelope v4 (ring AEAD) dual-read — **Status: pending**
- [ ] Kill TRXH HMAC-CTR handroll; zeroize keys; v3/v4 dual-read window

## Phase W5: Passes hot-loop ports (per-pass diff-fuzz) — **Status: pending**

## Phase W6: Native .pyd/.so + self-extracting .py + standalone .exe embed — **Status: pending**

## Phase W7: Hardening (asm stubs TEB/syscall, cargo-deny/audit, strip, build-ID rotation) — **Status: pending**

---

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Single-engine architecture; emergency py-interpreter auto-generated+CI-verified | unlimited-resources best answer; kills double-maintenance |
| CPython ast = only semantic truth | parity guarantees live on it |
| Packet format versioned; dual-read windows | lesson from crypto-envelope v4 rollback |
| Windows-first; 3 outputs incl NEW .pyc | user directive 2026-08-26 |
| --preset/--out-format additive flags; defaults unchanged | no-functionality-loss invariant |
| Agents own NEW files only; main owns shared-file edits | parallel conflict-free |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| pip hypothesis IncompleteRead (network) | 1 | retried by agent A2 -> installed 6.165.10 |
| template indent drift caused emitted IndentationError | perf wave G1 | fixed by matching HEAD indentation exactly |

## Next Step
Finish W1 gates then start W2 (trx-ir crate skeleton).
