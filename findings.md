# Findings: TVM Research & Upgrade

## Architecture
- TVM compiler: `_TVMASTCompiler` (~L5800-7500), AST → custom ISA bytecode
- Runtime: emitted f-string `src` (~L7700-8900), self-contained interpreter
- Envelope: v3 embedded-seed (master_seed + runtime_salt as repr() literals) = tamper-resistance only
- Dispatch: 256-slot trap-default table, per-build ISA shuffle + affine transform

## Key Bugs Found & Fixed
- visit_AsyncFunctionDef never finalized code object → crash on ALL async def
- posonlyargs silently dropped from signatures
- emit() had no 16-bit arg guard → silent jump corruption
- break/continue crossing try/with left stale exc_handlers entries
- from pkg.sub import name returned ROOT package (no fromlist)
- except* compiled as plain try (silent PEP 654 destruction)
- Match sequence only accepted exact tuple/list; mapping only exact dict

## Anti-Fingerprint Status
| Token | Status |
|---|---|
| __TVM_LAZY__ | ✅ Tokenized |
| _NO_ARG | ✅ Tokenized |
| __vm_await__ | ✅ Tokenized |
| __vm_anext__ | ✅ Tokenized |
| __vm_match_rest__ | ✅ Tokenized |
| __vm_bind_defaults__ | ✅ Tokenized |
| __tvmfl__ | ✅ Tokenized |
| TRX_TVM_ENC/MAC_KEY_V3 | ⚠️ Protocol label, 2 occurrences |
| _h_* handler names | ⚠️ Deferred TVM 5.1 |
| trx_tvm_N monitoring | ✅ Random tag |

## Research Repo Insights
- bedrock: meta-packet hides ISA/M/A; eligibility gates; OFB domain-separated keys
- pyshield: depth-aware handler unwind; real cells via lambda closure; per-build Fisher-Yates
- HydraPy: static validator at load; honest threat model docs
- VMObfuscate: relative jumps survive block permutation

## License Matrix
- MIT (free): Anubis, HydraPy, Intensio, PyObfuscate, pyshield
- Apache-2.0: Opy
- EPL-2.0: Hyperion (vendored by Tr0ngX)
- Conditional: bedrock (Apache + provisions)
- DO NOT COPY: ObfuXtreme (AGPL), pybear/python-vm/pyminifier (GPL), pyarmor (EULA), MartyVM/VMObfuscate (no license)
