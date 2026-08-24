# Task Plan: TVM 5.0 Full Syntax Parity + Hardening

## Status: IN_PROGRESS
## Goal: Fix all 12 remaining VM weaknesses + comprehensive syntax test suite
## Branch: main (direct)

---

## Phase 1: Quick Wins — Signature & Defaults (LOW RISK)
**Scope:** Compiler-side only, no runtime changes needed

- [ ] 1a. `/` keyword-rejection runtime enforcement
  - Serializer: add `posonly_count` field to tuple (index 10)
  - Runtime `code_obj.__init__`: read `data[10]`
  - Binder: check `_rem_kwargs` keys against `arg_names[:posonly_count]`
  - File: serializer ~L7645, runtime code_obj ~L7950, binder ~L8500

- [x] 1b. Lambda/kwonly defaults early-bind
  - [x] Kwonly defaults: already serialized via `kwonly_default_names` field
  - [x] Binder exempts kwonly-with-defaults from missing-arg check
  - [ ] Lambda defaults: move from inline preamble to def-time channel
    - In `visit_Lambda`: emit `(names_tuple, values_tuple)` before MAKE_FUNCTION bit3
    - Remove inline `_NO_ARG` preamble from lambda body
  - File: visit_Lambda ~L6595

- [x] 1c. `del nonlocal_var` cell reset
  - When deleting a nonlocal var that's a cell: set `[sentinel]` instead of local del
  - Need compiler to know which names are cells (from B2 below) OR use simpler heuristic
  - Interim fix: DEL_DEREF handler checks if parent frame has the name → pop from there
  - File: `_h_d_fast` or add DEL_DEREF handler if not exists

- [x] 1d. `super()` metadata compile-time
  - In `visit_FunctionDef`: when inside ClassDef context, attach `defining_class` name
  - Runtime: zero-arg `super()` reads `_wrapped._vm_def_cls` + `arg_names[0]` directly
  - Already partially working (`_vm_def_cls` exists); just improve heuristic:
    - Use explicit self param index instead of "first non-None arg"
    - Skip None/sentinel values cleanly
  - File: visit_ClassDef ~L6833, vm_super_fn ~L8592

**Verify:** fn_args_matrix L1-L4 + oracle 31/31

---

## Phase 2: Import Completion (MEDIUM RISK)
**Scope:** New sentinel forms + handler extensions

- [ ] 2a. Star-import support (`from X import *`)
  - Sentinel: `'__tvmstar__' + module_name`
  - Runtime helper `__tvm_star_load__(mod_obj, global_env)`:
    ```python
    def __tvm_star_load__(_m, _g):
        _all = getattr(_m, '__all__', None)
        if _all:
            for k in _all: _g[k] = getattr(_m, k)
        else:
            for k, v in vars(_m).items():
                if not k.startswith('_'): _g[k] = v
    ```
  - Compiler: `visit_ImportFrom` when `alias.name == '*'`:
    emit IMPORT_NAME(sentinel) → STORE_GLOBAL(temp) → LOAD_GLOBAL(helper) → LOAD_GLOBAL(temp) → LOAD_GLOBAL(globals_dict) → CALL_FUNCTION(2) → POP_TOP
  - Register helper in emitted source near other helpers

- [ ] 2b. Relative import resolution (`from .pkg import x`)
  - Sentinel: `'__tvmrel__\x01<level>\x00<module>\x00<names_csv>'`
  - Handler resolves via `frame.global_env.get('__package__', '')`:
    - level=1: base = `__package__`
    - level=2: base = `__package__.rsplit('.', 1)[0]`
    - Then `__import__(base + '.' + module, fromlist=names)`
  - Fallback: ImportError native-shape if `__package__` absent

- [ ] 2c. `import a.b as c` without dotted-as (already works) + verify no regression
  - Just add test case

**Verify:** stmt_import_forms coverage case + new star/relative cases

---

## Phase 3: Exception Completion (HIGH VALUE)
**Scope:** except* real implementation

- [ ] 3a. `except*` PEP 654 real lowering
  - Replace `raise TVMEmitError(...)` in visit_TryStar with actual implementation
  - Runtime helper `__tvm_excg_split__(exc, exc_type)`:
    ```python
    def __tvm_excg_split__(exc, etype):
        if isinstance(exc, BaseExceptionGroup):
            return exc.split(etype)
        return (None, exc)  # non-group: no match
    ```
  - Compiler emission for `try/except* T as e/else/finally`:
    1. SETUP_FINALLY handler_lbl
    2. Body (same as regular try)
    3. POP_BLOCK; JUMP finally_or_end
    4. handler_lbl: STORE_FAST exc_slot
    5. For each except* clause:
       - CALL __tvm_excg_split__(exc_slot, T)
       - UNPACK_SEQUENCE 2 → matched, rest
       - JUMP_IF_FALSE next_handler
       - STORE_FAST rest_slot (replace original)
       - If as-name: STORE capture from matched
       - Emit handler body
       - After body: if rest is not None: RAISE rest
       - JUMP end
    6. next_handler: LOAD_FAST rest_slot; STORE_FAST exc_slot (for next iteration)
    7. All handlers done + rest still set: RAISE exc_slot
    8. end:
  - Prohibitions (compile-time AST walk):
    - No return/break/continue inside except* body
    - Cannot mix except* and plain except on same try
  - Note: `except*` requires Python 3.11+; gate on sys.version_info

- [ ] 3b. Return/break-in-finally splice (GAP-02)
  - Compiler maintains `self._fin_stack: List[List[stmt]]`
  - Push `node.finalbody` when entering try-with-finally
  - Pop after try completes
  - `visit_Return`: before RETURN_VALUE, deep-copy + emit each fin_stack entry (inner→outer order)
  - `visit_Break`/`visit_Continue`: same splicing before JUMP
  - Edge: `continue` inside its own finally → compile-block (CPython prohibits)
  - Uses `copy.deepcopy` for finalbody statements to avoid label collision

**Verify:** oracle 06 (try_except_finally) + new exc_group cases

---

## Phase 4: Closure Cell Boxing (HIGHEST COMPLEXITY)
**Scope:** Replaces captured_env dict-snapshot with real cell objects

- [ ] 4a. Compile-time free-variable analysis
  - Extend `_scan_scope` to compute per-function:
    - `cell_vars: Set[str]` — names assigned here AND loaded by nested functions
    - `free_vars: Set[str]` — names loaded here but assigned in enclosing scope
  - Algorithm: recursive walk of FunctionDef children (not descending into inner defs for assignment tracking, but collecting their Load references)

- [ ] 4b. Emission changes
  - Prologue: `_cells = {n: [_NO_ARG_SENTINEL] for n in cell_vars}`
  - For each cell_var n:
    - STORE_FAST n → also sync `_cells[n][0] = val` after every store
    - LOAD_FAST n → prefer `_cells[n][0]` if bound, fallback to locals[n]
  - MAKE_FUNCTION: pass `_f.cells` reference (not dict copy) into closure env
  - Inner function prologue: merge `_captured_cells` into own `_cells`

- [ ] 4c. Runtime changes
  - Frame gains `self.cells = {}` attribute
  - bind_frame_fn: allocate cells for known cell_vars
  - MAKE_FUNCTION: propagate parent cells (reference share)
  - LOAD_DEREF/STORE_DEREF: operate on cells dict instead of active_frames walk

- [ ] 4d. `del nonlocal_var` → `_cells[n][0] = sentinel`

**Verify:** clo_late_binding, clo_deep_nest, clo_recursion_inner, closures oracle case
**Risk:** HIGH — touches every variable access path. Branch separately.
**Fallback:** If too complex, implement partial: only box variables that are ACTUALLY mutated by nested functions (detected at compile time), leave read-only captures as snapshot.

---

## Phase 5: Comprehensive Test Suite (PARALLEL with 1-4)
**Scope:** New test file, independent of engine changes

- [ ] 5a. Create `tests/test_vm_syntax_parity.py`
  - Reuse `case()` infrastructure from test_vm_full_coverage.py
  - ~40 stress cases across 7 categories (see findings.md for full list)
  - Each case: native run vs obfuscated run at levels [1,2,3], stdout+exit match

- [ ] 5b. Categories:
  - Exception edge: exc_group_basic/nested, return_in_finally, break_in_finally, reraise_chain, custom_hierarchy
  - Closure stress: late_binding, deep_nest, recursion_inner, loop_capture, del_nonlocal, global_shadows
  - Generator/Async: send_throw_close, yield_from_delegate, infinite_take, async_gen, async_comp, async_with
  - OOP advanced: metaclass, descriptor, mro_diamond, slots_repr, abstract, dataclass_like
  - Control flow: nested_break_continue, try_in_loop_try, match_all_patterns, walrus_comp, ternary_chain, while_else
  - Imports: from_submodule, dotted_as, star_module, relative_pkg, mixed_types
  - Misc: lambda_defaults_shared, chained_compare, unpack_star_deep, dict_order_update, str_format_edge

- [ ] 5c. Wire into `tests/run_all_tests.py` Phase 3 standalone list

**Verify:** New suite passes independently + doesn't break existing suites

---

## Phase 6: Docs Sync + Final
- [ ] AGENTS §4.7 → §4.8 rewrite with full coverage matrix
- [ ] GEMINI mirror
- [ ] README feature table update
- [ ] Final commit + push

---

## Execution Order
```
Phase 5 (test suite) ── PARALLEL with Phase 1 ──► establishes baseline
Phase 1 (quick wins) ──► verify with Phase 5 subset
Phase 2 (imports)     ──► verify
Phase 3 (exceptions)  ──► verify
Phase 4 (cells)       ──► verify (branch, merge after green)
Phase 6 (docs)        ──► final
```

## Known Limitations (documented honestly even after this wave)
| Feature | Status |
|---|---|
| Generator lazy semantics | Partially emulated (eager list for genexpr) |
| Dynamic scope leak | _h_ld_g walks frames before globals |
| Thread safety | Single-threaded assumption |
| Performance overhead | 30-100x native (no pre-binding yet) |

## Errors & Blockers
(none currently)
