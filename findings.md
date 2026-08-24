# Findings: TVM 5.0 Final Wave

## Annotations Design
- `visit_AnnAssign` currently ignores node.annotation entirely
- Module/class level: need `__annotations__[name] = evaluated_annotation` after value assignment
- Function level: annotations dict built at def-time, attached via `fn.__annotations__`
- CPython stores param anns in `co_annotations` bytecode (3.11+) but we can use a simpler dict
- Flag default=n: avoids bloat + side effects (annotation evaluation may import modules)
- When y: annotation expressions ARE evaluated (matching CPython behavior where module-level annotations are stored)

## Anti-Intercept Design
- Detection vectors: monkeypatched socket, fake CA certs, proxy env vars, interception module imports
- Countermeasure: pin original socket.socket reference, periodic integrity check via watchdog
- Integration point: same as antidebug — prepend shield source before compile packaging
- Must NOT break legitimate proxies (only flag localhost MITM ports commonly used by tools)
- False positive risk: corporate environments use real proxies on port 8080 → only flag when BOTH localhost AND non-system CA detected

## Key Insight: Annotation emission is compiler-only change
- No new opcodes needed; reuse STORE_SUBSCR for __annotations__ updates
- No runtime helper needed if we emit inline dict operations
- Function annotations need one small helper to set fn.__annotations__ after MAKE_FUNCTION
