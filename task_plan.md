# Task Plan: TVM 5.0 Final — Annotations + Deep Anti-Intercept Shield

## Status: IN_PROGRESS
## Goal: Add --vm-annotations opt-in + --anti-intercept DEEP shield

---

## Phase 1: Annotations Support (--vm-annotations y/n)
**Scope:** Compiler-side only, no runtime changes needed beyond __annotations__ dict

- [ ] 1a. CLI flag `--vm-annotations` y/n default n
  - File: argparse section ~L10300, engine state wiring ~L10500

- [ ] 1b. Module-level annotated assignments: `x: int = 5`
  - visit_AnnAssign: if flag on → evaluate annotation value → store into `__annotations__` dict via STORE_SUBSCR on LOAD_GLOBAL __annotations__
  - If flag off → current behavior (just assign value)

- [ ] 1c. Class-body annotated assignments: `attr: str = "val"`
  - Same as module level but inside class namespace

- [ ] 1d. Function parameter + return annotations
  - visit_FunctionDef/AsyncFunctionDef/Lambda: collect param.annotation + node.returns
  - If flag on: after MAKE_FUNCTION, emit CALL __tvm_set_annotations__(fn_obj, ann_dict)
  - Runtime helper builds {param_name: type_value, 'return': ret_type}

- [ ] 1e. Runtime helper `__tvm_set_annotations__`
  - Takes function object + annotations dict → sets fn.__annotations__

- [ ] 1f. Verify: dataclass-like pattern works when flag=y; no bloat when flag=n

## Phase 2: Deep Anti-Intercept Shield (--anti-intercept y/n)
**Scope:** New runtime shield injected like antidebug/antivm

- [ ] 2a. CLI flag `--anti-intercept` y/n default n

- [ ] 2b. Network interception tool detection (runtime):
  - Module blacklist scan: mitmproxy, scapy, httpretty, responses, requests_mock, unittest.mock.patch('requests.get'), pyproxy, proxy.py
  - Socket wrapper detection: check if `socket.socket` has been monkeypatched (compare id vs fresh import)
  - SSL context tampering: verify ssl.create_default_context hasn't been replaced
  - Environment variable probes: HTTP_PROXY/HTTPS_PROXY set to localhost MITM ports (8080, 8888, 9090)
  - Certificate authority injection: scan ssl.get_default_verify_paths() for non-system CA certs

- [ ] 2c. Active countermeasures:
  - Pin SSL context at import time before any user code runs
  - Snapshot socket.socket original reference; periodic verification
  - Block imports of known interception modules via sys.meta_path hook
  - If interception detected → _obliterate() (same as antidebug)

- [ ] 2d. Integration into pipeline
  - Insert alongside antidebug shield (before compile packaging)
  - Wire flag through options dict + get_args_or_prompt

## Phase 3: Docs Sync
- [ ] AGENTS.md: new flags table entries + §4.8 coverage matrix
- [ ] GEMINI.md mirror
- [ ] README feature table

## Verify
- [ ] vm_oracle 31/31 (no regression from annotation emission when off)
- [ ] vm_full_coverage 156/156
- [ ] syntax_parity 66/66
- [ ] New test cases for annotations (flag=y produces correct __annotations__)
- [ ] New test case for anti-intercept (detects mock interception)
